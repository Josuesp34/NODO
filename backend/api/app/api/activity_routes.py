import hashlib
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import JSONResponse
from garmin_fit_sdk import Decoder, Stream
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.api.activity_schemas import ActivityLink
from app.api.dependencies import current_user
from app.api.routes import parse_fit, sensor_value
from app.core.config import settings
from app.core.database import get_db
from app.domain.comparison import compare_workout, local_day
from app.domain.metrics import calculate_banister_trimp
from app.infrastructure.database.models import Activity, PrescribedWorkout, TelemetryRecord, User
from app.infrastructure.database.models.product import (
    ActivityLap,
    AthleteProfile,
    Consent,
    DailyLoad,
    IngestionEvent,
    Job,
)
from app.services import object_store
from app.services.access import require_athlete_access
from app.services.audit import add_audit

router = APIRouter(prefix="/athletes/{athlete_id}/activities", tags=["Activities"])


def fit_laps(content: bytes) -> tuple[list[dict], str]:
    decoder = Decoder(Stream.from_byte_array(bytearray(content)))
    messages, errors = decoder.read()
    if errors:
        raise ValueError("El archivo FIT contiene errores de decodificación")
    sessions = messages.get("session_mesgs", [])
    sport_raw = str(sessions[0].get("sport", "unknown")) if sessions else "unknown"
    sport_map = {
        "run": "running",
        "running": "running",
        "cycling": "cycling",
        "bike": "cycling",
        "swimming": "swimming",
        "swim": "swimming",
        "triathlon": "triathlon",
    }
    laps = []
    for index, raw in enumerate(messages.get("lap_mesgs", [])):
        laps.append(
            {
                "lap_index": index,
                "started_at": raw.get("start_time"),
                "duration_sec": raw.get("total_timer_time"),
                "distance_m": raw.get("total_distance"),
                "avg_heart_rate": raw.get("avg_heart_rate"),
                "avg_power": raw.get("avg_power"),
            }
        )
    return laps, sport_map.get(sport_raw.lower(), "unknown")


async def current_profile(
    db: AsyncSession, athlete_id: int, at: datetime, timezone: str = "UTC"
) -> AthleteProfile | None:
    return await db.scalar(
        select(AthleteProfile)
        .where(
            AthleteProfile.athlete_id == athlete_id,
            AthleteProfile.valid_from <= date.fromisoformat(local_day(at, timezone)),
            (
                AthleteProfile.valid_to.is_(None)
                | (AthleteProfile.valid_to >= date.fromisoformat(local_day(at, timezone)))
            ),
        )
        .order_by(AthleteProfile.valid_from.desc())
        .limit(1)
    )


@router.post("/fit", status_code=status.HTTP_201_CREATED)
async def upload_fit(
    athlete_id: int,
    file: UploadFile = File(...),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    athlete = await require_athlete_access(db, user, athlete_id)
    if settings.ENVIRONMENT != "development":
        consent = await db.scalar(
            select(Consent.id).where(
                Consent.user_id == athlete_id,
                Consent.scope == "training_data_processing",
                Consent.revoked_at.is_(None),
            )
        )
        if consent is None:
            raise HTTPException(403, "CONSENT_REQUIRED")
    if not file.filename or not file.filename.lower().endswith(".fit"):
        raise HTTPException(400, "Extensión inválida, debe ser .fit")
    content = await file.read(settings.MAX_FIT_BYTES + 1)
    if len(content) > settings.MAX_FIT_BYTES:
        raise HTTPException(413, "Archivo FIT demasiado grande")
    file_hash = hashlib.sha256(content).hexdigest()
    existing = await db.scalar(
        select(Activity).where(
            Activity.athlete_id == athlete_id,
            Activity.file_hash == file_hash,
        )
    )
    if existing is not None:
        if object_store.enabled() or settings.ENVIRONMENT != "development":
            try:
                await object_store.put_file(f"fit/{athlete_id}/{file_hash}.fit", content)
            except object_store.ObjectStoreError:
                raise HTTPException(503, "No se pudo conservar el archivo privado; puedes reintentar") from None
        return JSONResponse(
            status_code=200,
            content={"status": "already_imported", "activity_id": existing.id, "file_hash": file_hash},
        )
    try:
        (df, metrics), (laps, sport_type) = await run_in_threadpool(lambda: (parse_fit(content), fit_laps(content)))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    started_at = df["timestamp"].iloc[0].to_pydatetime()
    profile = await current_profile(db, athlete_id, started_at, athlete.timezone)
    trimp_value = None
    trimp_status = "insufficient_inputs"
    if (
        profile is not None
        and profile.rest_hr is not None
        and profile.max_hr is not None
        and profile.trimp_variant is not None
        and metrics["trimp_inputs_available"]
    ):
        trimp_value = calculate_banister_trimp(
            metrics["duration_min"],
            metrics["avg_hr"],
            profile.rest_hr,
            profile.max_hr,
            profile.trimp_variant == "banister_male",
        )
        trimp_status = "calculated"
    external_id = f"manual_fit:{athlete_id}:{file_hash}"
    event = IngestionEvent(
        athlete_id=athlete_id,
        provider="manual_fit",
        external_id=external_id,
        payload_hash=file_hash,
        status="processing",
    )
    db.add(event)
    activity = Activity(
        athlete_id=athlete_id,
        file_name=Path(file.filename).name[:255],
        file_hash=file_hash,
        provider="manual_fit",
        external_id=external_id,
        sport_type=sport_type,
        timezone=athlete.timezone,
        start_time=started_at,
        total_duration_sec=metrics["duration_min"] * 60,
        total_distance_m=metrics.get("distance_m"),
        avg_speed_mps=metrics.get("avg_speed_mps"),
        avg_heart_rate=round(metrics["avg_hr"]) if metrics["avg_hr"] is not None else None,
        max_heart_rate=metrics["max_hr"],
        calculated_trimp=trimp_value,
    )
    db.add(activity)
    try:
        await db.flush()
        db.add_all(
            [
                TelemetryRecord(
                    activity_id=activity.id,
                    timestamp=row["timestamp"].to_pydatetime(),
                    heart_rate=sensor_value(row, "heart_rate", integer=True, minimum=1),
                    altitude=sensor_value(row, "enhanced_altitude", "altitude", minimum=-15000),
                    speed_ms=sensor_value(row, "enhanced_speed", "speed"),
                    cadence=sensor_value(row, "cadence", integer=True),
                    power=sensor_value(row, "power", integer=True),
                    temperature=sensor_value(row, "temperature", integer=True, minimum=-100),
                )
                for _, row in df.iterrows()
            ]
        )
        db.add_all([ActivityLap(activity_id=activity.id, **lap) for lap in laps])
        event.status = "processed"
        job_key = f"daily-load:{athlete_id}:{local_day(started_at, athlete.timezone)}"
        job = await db.scalar(select(Job).where(Job.dedupe_key == job_key))
        if job is None:
            db.add(
                Job(
                    kind="recalculate_daily_load",
                    payload={"athlete_id": athlete_id, "from_date": str(local_day(started_at, athlete.timezone))},
                    run_after=datetime.now(UTC),
                    max_attempts=settings.JOB_MAX_ATTEMPTS,
                    dedupe_key=job_key,
                )
            )
        else:
            job.status = "pending"
            job.run_after = datetime.now(UTC)
            job.last_error = None
        add_audit(
            db,
            actor_id=user.id,
            entity="activity",
            entity_id=activity.id,
            action="import_fit",
            after={"athlete_id": athlete_id, "file_hash": file_hash, "provider": "manual_fit"},
        )
        if object_store.enabled() or settings.ENVIRONMENT != "development":
            await object_store.put_file(f"fit/{athlete_id}/{file_hash}.fit", content)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing = await db.scalar(
            select(Activity).where(
                Activity.athlete_id == athlete_id,
                Activity.file_hash == file_hash,
            )
        )
        if existing is None:
            raise HTTPException(409, "No se pudo resolver la importación duplicada") from None
        return JSONResponse(
            status_code=200,
            content={"status": "already_imported", "activity_id": existing.id, "file_hash": file_hash},
        )
    except object_store.ObjectStoreError:
        await db.rollback()
        raise HTTPException(503, "No se pudo conservar el archivo privado; puedes reintentar") from None
    except Exception:
        await db.rollback()
        raise HTTPException(500, "No se pudo guardar la actividad") from None
    return {
        "status": "imported",
        "activity_id": activity.id,
        "file_hash": file_hash,
        "sport_type": sport_type,
        "trimp_status": trimp_status,
        "trimp_score": trimp_value,
        "telemetry_points_saved": len(df),
        "laps_saved": len(laps),
    }


def activity_view(item: Activity) -> dict:
    return {
        "id": item.id,
        "sport_type": item.sport_type,
        "started_at": item.start_time,
        "local_date": local_day(item.start_time, item.timezone),
        "timezone": item.timezone,
        "duration_sec": item.total_duration_sec,
        "distance_m": item.total_distance_m,
        "trimp": item.calculated_trimp,
        "tss": item.calculated_tss,
        "provider": item.provider,
        "version": item.version,
        "prescribed_workout_id": item.prescribed_workout_id,
        "quality": "partial" if item.total_distance_m is None else "good",
    }


@router.get("")
async def list_activities(
    athlete_id: int,
    response: Response,
    limit: int = Query(default=50, ge=1, le=250),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_athlete_access(db, user, athlete_id)
    total = await db.scalar(select(func.count()).select_from(Activity).where(Activity.athlete_id == athlete_id))
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Next-Offset"] = str(offset + limit) if offset + limit < total else ""
    rows = await db.scalars(
        select(Activity)
        .where(Activity.athlete_id == athlete_id)
        .order_by(Activity.start_time.desc(), Activity.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return [activity_view(item) for item in rows]


@router.get("/page")
async def activity_page(
    athlete_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    response = Response()
    items = await list_activities(athlete_id, response, limit, offset, user, db)
    return {
        "items": items,
        "total": int(response.headers["X-Total-Count"]),
        "next_offset": int(response.headers["X-Next-Offset"]) if response.headers["X-Next-Offset"] else None,
    }


async def comparison_for_athlete(db: AsyncSession, user: User, athlete_id: int, start: date, end: date):
    athlete = await require_athlete_access(db, user, athlete_id)
    if end < start or (end - start).days > 92:
        raise HTTPException(422, "El rango debe abarcar entre 1 y 93 días")
    workouts = list(
        await db.scalars(
            select(PrescribedWorkout)
            .where(
                PrescribedWorkout.athlete_id == athlete_id,
                PrescribedWorkout.status == "published",
                # Bound in UTC with a one-day margin; final selection uses the athlete's local day.
                PrescribedWorkout.scheduled_date >= datetime.combine(start - timedelta(days=1), datetime.min.time()),
                PrescribedWorkout.scheduled_date < datetime.combine(end + timedelta(days=2), datetime.min.time()),
            )
            .order_by(PrescribedWorkout.scheduled_date, PrescribedWorkout.id)
        )
    )
    workouts = [w for w in workouts if str(start) <= local_day(w.scheduled_date, athlete.timezone) <= str(end)]
    # Include linked late imports regardless of their recorded date.
    activities = list(
        await db.scalars(
            select(Activity)
            .where(
                Activity.athlete_id == athlete_id,
                or_(
                    Activity.start_time.between(
                        datetime.combine(start - timedelta(days=1), datetime.min.time()),
                        datetime.combine(end + timedelta(days=2), datetime.min.time()),
                    ),
                    Activity.prescribed_workout_id.in_([w.id for w in workouts]),
                ),
            )
            .order_by(Activity.id)
        )
    )
    relevant = [
        a
        for a in activities
        if str(start) <= local_day(a.start_time, athlete.timezone) <= str(end)
        or a.prescribed_workout_id in {w.id for w in workouts}
    ]
    laps = (
        list(
            await db.scalars(
                select(ActivityLap)
                .where(ActivityLap.activity_id.in_([a.id for a in relevant]))
                .order_by(ActivityLap.activity_id, ActivityLap.lap_index)
            )
        )
        if relevant
        else []
    )
    by_workout, by_activity = {}, {}
    for item in relevant:
        by_workout.setdefault(item.prescribed_workout_id, []).append(item)
    for lap in laps:
        by_activity.setdefault(lap.activity_id, []).append(lap)
    observed_days = {local_day(a.start_time, athlete.timezone) for a in relevant if a.calculated_trimp is not None}
    result = []
    for workout in workouts:
        linked = by_workout.get(workout.id, [])
        row = {
            "workout_id": workout.id,
            "title": workout.title,
            "sport_type": workout.sport_type,
            "local_date": local_day(workout.scheduled_date, athlete.timezone),
            "activities": [activity_view(a) for a in linked],
        }
        if len(linked) == 1:
            row.update(compare_workout(workout, linked[0], by_activity.get(linked[0].id, [])))
        else:
            row.update(
                status="not_synchronized" if not linked else "ambiguous_multiple_activities",
                summary=[],
                laps=[],
                reason="Sin vínculo confirmado; la falta de datos no es incumplimiento.",
            )
        result.append(row)
    loads = list(
        await db.scalars(
            select(DailyLoad)
            .where(DailyLoad.athlete_id == athlete_id, DailyLoad.local_date.between(start, end))
            .order_by(DailyLoad.local_date, DailyLoad.load_unit)
        )
    )
    return {
        "timezone": athlete.timezone,
        "start": start,
        "end": end,
        "workouts": result,
        "unlinked_activities": [activity_view(a) for a in relevant if a.prescribed_workout_id is None],
        "daily_load": [
            {
                "local_date": x.local_date,
                "value": x.load_value if str(x.local_date) in observed_days else None,
                "unit": x.load_unit,
                "formula_version": x.formula_version,
                "quality": "recorded" if str(x.local_date) in observed_days else "not_observed",
            }
            for x in loads
        ],
    }


@router.get("/comparison")
async def activity_comparison(
    athlete_id: int, start: date, end: date, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    return await comparison_for_athlete(db, user, athlete_id, start, end)


@router.get("/{activity_id}")
async def activity_detail(
    athlete_id: int, activity_id: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    await require_athlete_access(db, user, athlete_id)
    item = await db.scalar(select(Activity).where(Activity.id == activity_id, Activity.athlete_id == athlete_id))
    if item is None:
        raise HTTPException(404, "Actividad no encontrada")
    laps = list(
        await db.scalars(select(ActivityLap).where(ActivityLap.activity_id == item.id).order_by(ActivityLap.lap_index))
    )
    return {
        **activity_view(item),
        "laps": [
            {
                "index": lap.lap_index,
                "duration_sec": lap.duration_sec,
                "distance_m": lap.distance_m,
                "avg_heart_rate": lap.avg_heart_rate,
                "avg_power": lap.avg_power,
            }
            for lap in laps
        ],
        "telemetry_points": await db.scalar(
            select(func.count()).select_from(TelemetryRecord).where(TelemetryRecord.activity_id == item.id)
        ),
    }


@router.put("/{activity_id}/link")
async def link_activity(
    athlete_id: int,
    activity_id: int,
    payload: ActivityLink,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_athlete_access(db, user, athlete_id)
    item = await db.scalar(select(Activity).where(Activity.id == activity_id, Activity.athlete_id == athlete_id))
    if item is None:
        raise HTTPException(404, "Actividad no encontrada")
    if payload.prescribed_workout_id is not None:
        workout = await db.scalar(
            select(PrescribedWorkout).where(
                PrescribedWorkout.id == payload.prescribed_workout_id,
                PrescribedWorkout.athlete_id == athlete_id,
                PrescribedWorkout.status == "published",
            )
        )
        if workout is None:
            raise HTTPException(404, "Sesión publicada no encontrada")
        if workout.sport_type != item.sport_type:
            raise HTTPException(422, "Las disciplinas no coinciden")
    before = item.prescribed_workout_id
    changed = await db.execute(
        update(Activity)
        .where(Activity.id == item.id, Activity.version == payload.expected_version)
        .values(prescribed_workout_id=payload.prescribed_workout_id, version=payload.expected_version + 1)
    )
    if changed.rowcount != 1:
        raise HTTPException(409, "El vínculo cambió; recarga la actividad")
    add_audit(
        db,
        actor_id=user.id,
        entity="activity",
        entity_id=item.id,
        action="link",
        before={"prescribed_workout_id": before},
        after=payload.model_dump(),
    )
    await db.commit()
    await db.refresh(item)
    return activity_view(item)
