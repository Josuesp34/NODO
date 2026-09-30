import asyncio
import json
import logging
import os
import socket
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_maker
from app.domain.metrics import calculate_training_status
from app.infrastructure.database.models import Activity, User
from app.infrastructure.database.models.operations import WorkerHeartbeat
from app.infrastructure.database.models.product import DailyLoad, Job
from app.services.email import send_queued_email

logger = logging.getLogger("nodo.worker")


async def recompute_daily_load(db: AsyncSession, athlete_id: int, from_date: date) -> None:
    athlete = await db.get(User, athlete_id)
    if athlete is None:
        raise ValueError("Atleta inexistente")
    timezone = ZoneInfo(athlete.timezone)
    activities = (
        await db.scalars(select(Activity).where(Activity.athlete_id == athlete_id).order_by(Activity.start_time))
    ).all()
    loads_by_day: dict[date, float] = {}
    for activity in activities:
        local_day = activity.start_time.astimezone(timezone).date()
        if local_day < from_date:
            continue
        value = activity.calculated_trimp
        if value is None:
            continue
        loads_by_day[local_day] = loads_by_day.get(local_day, 0.0) + value
    previous = await db.scalar(
        select(DailyLoad)
        .where(
            DailyLoad.athlete_id == athlete_id,
            DailyLoad.local_date < from_date,
            DailyLoad.load_unit == "trimp",
        )
        .order_by(DailyLoad.local_date.desc())
        .limit(1)
    )
    ctl = previous.ctl if previous else 0.0
    atl = previous.atl if previous else 0.0
    await db.execute(
        delete(DailyLoad).where(
            DailyLoad.athlete_id == athlete_id,
            DailyLoad.local_date >= from_date,
            DailyLoad.load_unit == "trimp",
        )
    )
    from app.domain.comparison import daily_load_horizon

    final_day = daily_load_horizon(from_date, loads_by_day, datetime.now(UTC), athlete.timezone)
    day = from_date
    now = datetime.now(UTC)
    while day <= final_day:
        state = calculate_training_status(loads_by_day.get(day, 0.0), ctl, atl)
        ctl, atl = state["ctl"], state["atl"]
        db.add(
            DailyLoad(
                athlete_id=athlete_id,
                local_date=day,
                load_unit="trimp",
                load_value=loads_by_day.get(day, 0.0),
                ctl=ctl,
                atl=atl,
                tsb=state["tsb"],
                formula_version="ewma-42-7-v1",
                recomputed_at=now,
            )
        )
        day += timedelta(days=1)


async def claim_jobs(db: AsyncSession, worker_id: str) -> list[Job]:
    stale_before = datetime.now(UTC) - timedelta(minutes=5)
    jobs = (
        await db.scalars(
            select(Job)
            .where(
                Job.run_after <= datetime.now(UTC),
                (Job.status == "pending") | ((Job.status == "running") & (Job.locked_at < stale_before)),
            )
            .order_by(Job.run_after, Job.id)
            .limit(settings.WORKER_BATCH_SIZE)
            .with_for_update(skip_locked=True)
        )
    ).all()
    for job in jobs:
        job.status = "running"
        job.locked_by = worker_id
        job.locked_at = datetime.now(UTC)
        job.attempts += 1
    await db.commit()
    return jobs


async def execute_job(db: AsyncSession, job: Job) -> None:
    try:
        if job.kind == "recalculate_daily_load":
            await recompute_daily_load(
                db,
                int(job.payload["athlete_id"]),
                date.fromisoformat(job.payload["from_date"]),
            )
        elif job.kind == "send_resend_email":
            await send_queued_email(job)
            # Reducir retención de PII incluso cifrada tras la entrega.
            job.payload = {"delivered": True}
        elif job.kind == "intervals_sync":
            from app.services.intervals_real import execute_intervals_job

            await execute_intervals_job(db, job)
        elif job.kind == "intervals_disconnect":
            from app.services.intervals_real import execute_intervals_disconnect_job

            await execute_intervals_disconnect_job(db, job)
        elif job.kind == "send_web_push":
            from app.services.notifications import send_notification

            await send_notification(db, job)
        elif job.kind in {"privacy_retention", "privacy_delete_user_files", "privacy_delete_artifact"}:
            from app.services.privacy_jobs import dispatch_privacy_job

            await dispatch_privacy_job(db, job)
        else:
            raise ValueError(f"Tipo de trabajo no soportado: {job.kind}")
        job.status = "completed"
        job.last_error = None
        job.locked_at = None
        job.locked_by = None
        await db.commit()
        logger.info(json.dumps({"event": "job_completed", "kind": job.kind, "attempt": job.attempts}))
    except Exception as exc:
        await db.rollback()
        fresh = await db.get(Job, job.id)
        if fresh is None:
            return
        fresh.last_error = "Tipo de trabajo no soportado" if job.kind == "unsupported" else type(exc).__name__
        fresh.locked_at = None
        fresh.locked_by = None
        if fresh.attempts >= fresh.max_attempts:
            fresh.status = "dead"
        else:
            fresh.status = "pending"
            delay = settings.JOB_BACKOFF_BASE_SECONDS * (2 ** max(fresh.attempts - 1, 0))
            fresh.run_after = datetime.now(UTC) + timedelta(seconds=delay)
        await db.commit()
        logger.warning(json.dumps({"event": "job_failed", "kind": fresh.kind, "attempt": fresh.attempts, "status": fresh.status, "error_type": type(exc).__name__}))


async def run_once(worker_id: str | None = None) -> int:
    worker_id = worker_id or f"{socket.gethostname()}:{os.getpid()}"
    async with async_session_maker() as db:
        heartbeat = await db.get(WorkerHeartbeat, worker_id)
        if heartbeat is None:
            db.add(WorkerHeartbeat(worker_id=worker_id, last_seen_at=datetime.now(UTC)))
        else:
            heartbeat.last_seen_at = datetime.now(UTC)
        await db.commit()
        jobs = await claim_jobs(db, worker_id)
        for job in jobs:
            await execute_job(db, job)
        return len(jobs)


async def run_forever() -> None:
    logging.basicConfig(level=logging.INFO)
    while True:
        processed = await run_once()
        if processed == 0:
            await asyncio.sleep(settings.WORKER_POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(run_forever())
