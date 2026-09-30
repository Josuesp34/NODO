"""Typed, bounded, server-authorized reads. User notes are data, never instructions."""

from datetime import UTC, date, datetime, timedelta
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select

from app.infrastructure.database.models import Activity, PrescribedWorkout
from app.infrastructure.database.models.product import (
    ActivityLap,
    AthleteConnection,
    AthleteGroup,
    AthleteProfile,
    Checkin,
    CoachAthleteAssignment,
    Competition,
    Complaint,
    ComplaintUpdate,
    DailyLoad,
    GroupMembership,
    Observation,
    ReviewItem,
)
from app.services.access import require_athlete_access
from app.services.provider_policy import require_provider_consent

ToolName = Literal[
    "profile",
    "calendar",
    "activities",
    "comparison",
    "observations",
    "summary",
    "complaints",
    "review",
    "groups",
    "quality",
]
TOOLS = (
    "profile",
    "calendar",
    "activities",
    "comparison",
    "observations",
    "summary",
    "complaints",
    "review",
    "groups",
    "quality",
)


class ToolRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool: ToolName
    athlete_id: int = Field(gt=0)
    start: date = Field(default_factory=lambda: datetime.now(UTC).date() - timedelta(days=14))
    end: date = Field(default_factory=lambda: datetime.now(UTC).date() + timedelta(days=14))
    limit: int = Field(default=30, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=10000)

    @model_validator(mode="after")
    def bounded_period(self):
        if self.end < self.start or (self.end - self.start).days > 90:
            raise ValueError("El período debe ser ordenado y no superar 90 días")
        return self


def scalar(value):
    return value.isoformat() if isinstance(value, (date, datetime)) else value


def row_data(row, fields):
    return {field: scalar(getattr(row, field)) for field in fields}


def citation(tool, athlete_id, identifier):
    return {
        "key": f"{tool}:{athlete_id}:{identifier}",
        "entity": tool,
        "id": identifier,
        "athlete_id": athlete_id,
        "source": "nodo_db",
        "tool": tool,
    }


async def read_tool(db, user, args: ToolRead, role: str):
    athlete = await require_athlete_access(db, user, args.athlete_id)
    if role == "athlete" and athlete.id != user.id:
        raise HTTPException(404, "Atleta no encontrado")
    await require_provider_consent(db, athlete.id, "training_data_processing")
    aid, kind = athlete.id, args.tool
    start = datetime.combine(args.start, datetime.min.time(), UTC)
    end = datetime.combine(args.end + timedelta(days=1), datetime.min.time(), UTC)
    data, citations = [], []
    if kind == "comparison":
        # Integrated product package supplies the canonical typed comparison service.
        from app.api import activity_routes

        canonical = getattr(activity_routes, "comparison_for_athlete", None)
        if canonical is not None:
            result = await canonical(db, user, aid, args.start, args.end)
            return {
                "tool": kind,
                "athlete_id": aid,
                "data": [result],
                "citations": [citation(kind, aid, "period")],
                "next_offset": None,
                "start": str(args.start),
                "end": str(args.end),
            }
    if kind in {"comparison", "quality", "summary"}:
        # Use stored metrics and deterministic comparison; no model-computed physiological metrics.
        activities = (
            await db.scalars(
                select(Activity)
                .where(Activity.athlete_id == aid, Activity.start_time >= start, Activity.start_time < end)
                .order_by(Activity.start_time.desc())
                .offset(args.offset)
                .limit(args.limit + 1)
            )
        ).all()
        truncated = len(activities) > args.limit
        for activity in activities[: args.limit]:
            item = row_data(
                activity,
                [
                    "id",
                    "start_time",
                    "sport_type",
                    "provider",
                    "total_duration_sec",
                    "total_distance_m",
                    "calculated_trimp",
                    "calculated_tss",
                    "prescribed_workout_id",
                ],
            )
            workout = (
                await db.get(PrescribedWorkout, activity.prescribed_workout_id)
                if activity.prescribed_workout_id
                else None
            )
            if workout and (workout.athlete_id != aid or (role == "athlete" and workout.status != "published")):
                workout = None
            if kind == "comparison":
                item["prescription"] = (
                    row_data(workout, ["id", "version", "title", "steps", "target_duration_sec"]) if workout else None
                )
                item["duration_delta_sec"] = (
                    activity.total_duration_sec - workout.target_duration_sec
                    if workout and workout.target_duration_sec is not None and workout.sport_type == activity.sport_type
                    else None
                )
                item["comparison_quality"] = (
                    "compatible_duration" if item["duration_delta_sec"] is not None else "insufficient_data"
                )
            data.append(item)
            citations.append(citation(kind, aid, activity.id))
        loads = (
            await db.scalars(
                select(DailyLoad)
                .where(
                    DailyLoad.athlete_id == aid, DailyLoad.local_date >= args.start, DailyLoad.local_date <= args.end
                )
                .order_by(DailyLoad.local_date)
                .limit(100)
            )
        ).all()
        if kind == "summary":
            data.append(
                {
                    "checkins": [
                        row_data(r, ["local_date", "fatigue", "perceived_rest", "stress", "session_rpe", "notes"])
                        for r in (
                            await db.scalars(
                                select(Checkin)
                                .where(
                                    Checkin.athlete_id == aid,
                                    Checkin.local_date >= args.start,
                                    Checkin.local_date <= args.end,
                                )
                                .order_by(Checkin.local_date)
                                .limit(100)
                            )
                        ).all()
                    ],
                    "daily_load": [
                        row_data(r, ["local_date", "load_unit", "load_value", "ctl", "atl", "tsb", "formula_version"])
                        for r in loads
                    ],
                    "note": "Datos almacenados; ausencia de sincronización no es incumplimiento.",
                }
            )
            citations.append(citation(kind, aid, "stored_load"))
        if kind == "quality":
            connection = await db.scalar(
                select(AthleteConnection).where(
                    AthleteConnection.athlete_id == aid, AthleteConnection.provider == "intervals_icu"
                )
            )
            data.append(
                {
                    "connection_status": connection.status if connection else "not_connected",
                    "last_sync_at": scalar(connection.last_sync_at) if connection else None,
                }
            )
            data.append(
                {
                    "missing_load_count_in_page": sum(
                        a.calculated_trimp is None and a.calculated_tss is None for a in activities[: args.limit]
                    ),
                    "note": (
                        "No mezclar cargas de unidades/métodos distintos; wellness con método desconocido es parcial."
                    ),
                }
            )
            citations.append(citation(kind, aid, "quality"))
        return {
            "tool": kind,
            "athlete_id": aid,
            "data": data,
            "citations": citations,
            "offset": args.offset,
            "next_offset": args.offset + args.limit if truncated else None,
            "start": str(args.start),
            "end": str(args.end),
        }
    specs = {
        "profile": (
            AthleteProfile,
            [
                "id",
                "sports",
                "timezone",
                "goals",
                "availability",
                "rest_hr",
                "max_hr",
                "ftp",
                "threshold_pace_sec_per_km",
                "trimp_variant",
                "source",
                "valid_from",
                "valid_to",
            ],
            None,
        ),
        "calendar": (
            PrescribedWorkout,
            ["id", "title", "description", "scheduled_date", "sport_type", "status", "version", "steps"],
            PrescribedWorkout.scheduled_date,
        ),
        "activities": (
            Activity,
            [
                "id",
                "start_time",
                "sport_type",
                "provider",
                "timezone",
                "total_duration_sec",
                "total_distance_m",
                "avg_heart_rate",
                "calculated_trimp",
                "calculated_tss",
                "prescribed_workout_id",
            ],
            Activity.start_time,
        ),
        "observations": (
            Observation,
            [
                "id",
                "metric_type",
                "value",
                "unit",
                "method",
                "source",
                "observed_start",
                "observed_end",
                "timezone",
                "quality",
            ],
            Observation.observed_start,
        ),
        "complaints": (
            Complaint,
            ["id", "zone", "laterality", "intensity_0_10", "started_on", "limits_movement", "note", "status"],
            None,
        ),
        "review": (ReviewItem, ["id", "kind", "priority", "reason", "status", "decision_note"], None),
    }
    if kind == "groups":
        # Private organizational/group/coach notes are absent from athlete context.
        if role != "coach":
            return {"tool": kind, "athlete_id": aid, "data": [], "citations": [], "next_offset": None}
        rows = (
            await db.execute(
                select(AthleteGroup, GroupMembership)
                .join(GroupMembership, GroupMembership.group_id == AthleteGroup.id)
                .where(GroupMembership.athlete_id == aid, AthleteGroup.coach_id == user.id)
                .order_by(AthleteGroup.id)
                .offset(args.offset)
                .limit(args.limit + 1)
            )
        ).all()
        for group, membership in rows[: args.limit]:
            data.append({"id": group.id, "name": group.name, "overrides": membership.overrides})
            citations.append(citation(kind, aid, group.id))
    else:
        model, fields, period = specs[kind]
        query = select(model).where(model.athlete_id == aid)
        if period is not None:
            query = query.where(period >= start, period < end)
        if kind == "calendar" and role == "athlete":
            query = query.where(PrescribedWorkout.status == "published")
        if kind == "review" and role == "athlete":
            # Coach decision notes are private. Complaints have their own athlete-safe history.
            return {"tool": kind, "athlete_id": aid, "data": [], "citations": [], "next_offset": None}
        rows = (await db.scalars(query.order_by(model.id.desc()).offset(args.offset).limit(args.limit + 1))).all()
        for row in rows[: args.limit]:
            item = row_data(row, fields)
            if kind == "activities":
                laps = (
                    await db.scalars(
                        select(ActivityLap)
                        .where(ActivityLap.activity_id == row.id)
                        .order_by(ActivityLap.lap_index)
                        .limit(101)
                    )
                ).all()
                item["laps"] = [
                    row_data(
                        lap, ["lap_index", "started_at", "duration_sec", "distance_m", "avg_heart_rate", "avg_power"]
                    )
                    for lap in laps[:100]
                ]
                item["laps_truncated"] = len(laps) > 100
            if kind == "complaints":
                history = (
                    await db.scalars(
                        select(ComplaintUpdate)
                        .where(ComplaintUpdate.complaint_id == row.id)
                        .order_by(ComplaintUpdate.id)
                        .limit(101)
                    )
                ).all()
                item["updates"] = [
                    row_data(r, ["id", "intensity_0_10", "limits_movement", "note", "created_at"])
                    for r in history[:100]
                ]
                item["updates_truncated"] = len(history) > 100
            data.append(item)
            citations.append(citation(kind, aid, row.id))
        if kind == "profile":
            competitions = (
                await db.scalars(
                    select(Competition)
                    .where(
                        Competition.athlete_id == aid,
                        Competition.competition_date >= args.start,
                        Competition.competition_date <= args.end,
                    )
                    .limit(101)
                )
            ).all()
            data.append(
                {
                    "competitions": [
                        row_data(c, ["id", "name", "competition_date", "discipline", "priority"])
                        for c in competitions[:100]
                    ],
                    "competitions_truncated": len(competitions) > 100,
                }
            )
            if competitions:
                citations.append(citation(kind, aid, "competitions"))
    return {
        "tool": kind,
        "athlete_id": aid,
        "data": data,
        "citations": citations,
        "offset": args.offset,
        "next_offset": args.offset + args.limit if len(rows) > args.limit else None,
        "start": str(args.start),
        "end": str(args.end),
    }


async def full_context(db, user, thread):
    if thread.athlete_scope_id:
        athlete_ids = [thread.athlete_scope_id]
        extra = False
    else:
        athlete_ids = list(
            (
                await db.scalars(
                    select(CoachAthleteAssignment.athlete_id)
                    .where(CoachAthleteAssignment.coach_id == user.id, CoachAthleteAssignment.status == "active")
                    .order_by(CoachAthleteAssignment.athlete_id)
                    .limit(21)
                )
            ).all()
        )
        extra = len(athlete_ids) > 20
        athlete_ids = athlete_ids[:20]
    context, citations = [], []
    for aid in athlete_ids:
        for tool in TOOLS:
            result = await read_tool(db, user, ToolRead(tool=tool, athlete_id=aid), thread.role)
            context.append(result)
            for c in result["citations"]:
                c.update({"start": result.get("start"), "end": result.get("end")})
            citations.extend(result["citations"])
    return {"role": thread.role, "athletes_truncated": extra, "reads": context}, citations
