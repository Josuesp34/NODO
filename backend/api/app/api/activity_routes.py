import hashlib
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from garmin_fit_sdk import Decoder, Stream
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.api.dependencies import current_user
from app.api.routes import parse_fit, sensor_value
from app.core.config import settings
from app.core.database import get_db
from app.domain.metrics import calculate_banister_trimp
from app.infrastructure.database.models import Activity, TelemetryRecord, User
from app.infrastructure.database.models.product import (
    ActivityLap,
    AthleteProfile,
    Consent,
    IngestionEvent,
    Job,
)
from app.services.access import require_athlete_access
from app.services.audit import add_audit

router = APIRouter(prefix="/athletes/{athlete_id}/activities", tags=["Activities"])


def fit_laps(content: bytes) -> tuple[list[dict], str]:
    decoder = Decoder(Stream.from_byte_array(bytearray(content)))
    messages, errors = decoder.read()
    if errors:
        raise ValueError("El archivo FIT contiene errores de decodificación")
    sessions = messages.get("session_mesgs", [])
    sport_raw = str(sessions[0].get("sport", "running")) if sessions else "running"
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
    return laps, sport_map.get(sport_raw.lower(), "running")


async def current_profile(db: AsyncSession, athlete_id: int, at: datetime) -> AthleteProfile | None:
    return await db.scalar(
        select(AthleteProfile)
        .where(
            AthleteProfile.athlete_id == athlete_id,
            AthleteProfile.valid_from <= at.date(),
            (AthleteProfile.valid_to.is_(None) | (AthleteProfile.valid_to >= at.date())),
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
        return JSONResponse(
            status_code=200,
            content={"status": "already_imported", "activity_id": existing.id, "file_hash": file_hash},
        )
    try:
        (df, metrics), (laps, sport_type) = await run_in_threadpool(lambda: (parse_fit(content), fit_laps(content)))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    started_at = df["timestamp"].iloc[0].to_pydatetime()
    profile = await current_profile(db, athlete_id, started_at)
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
        job_key = f"daily-load:{athlete_id}:{started_at.date()}"
        job = await db.scalar(select(Job).where(Job.dedupe_key == job_key))
        if job is None:
            db.add(
                Job(
                    kind="recalculate_daily_load",
                    payload={"athlete_id": athlete_id, "from_date": str(started_at.date())},
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


@router.get("")
async def list_activities(
    athlete_id: int,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_athlete_access(db, user, athlete_id)
    rows = await db.scalars(
        select(Activity).where(Activity.athlete_id == athlete_id).order_by(Activity.start_time.desc()).limit(250)
    )
    return [
        {
            "id": item.id,
            "sport_type": item.sport_type,
            "started_at": item.start_time,
            "duration_sec": item.total_duration_sec,
            "trimp": item.calculated_trimp,
            "provider": item.provider,
            "prescribed_workout_id": item.prescribed_workout_id,
        }
        for item in rows.all()
    ]
