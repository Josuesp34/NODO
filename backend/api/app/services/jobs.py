import asyncio
import json
import logging
import os
import socket
import time
from contextlib import suppress
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import set_committed_value

from app.core.config import settings
from app.core.database import async_session_maker
from app.domain.metrics import calculate_training_status
from app.infrastructure.database.models import Activity, User
from app.infrastructure.database.models.operations import WorkerHeartbeat
from app.infrastructure.database.models.product import DailyLoad, Job
from app.services.email import send_queued_email

logger = logging.getLogger("nodo.worker")
last_health_emission = 0.0


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
            .execution_options(populate_existing=True)
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
    from app.services.notifications import PushDeferred
    from app.services.privacy_jobs import dispatch_privacy_job

    job_id, job_kind, owner, attempt = job.id, job.kind, job.locked_by, job.attempts
    claim = (Job.id == job_id, Job.status == "running", Job.locked_by == owner, Job.attempts == attempt)
    job = await db.scalar(select(Job).where(*claim).execution_options(populate_existing=True))
    if job is None:
        await db.rollback()
        return

    async def finish(values):
        # The handler may change payload/run_after; flush other entities only after
        # atomically proving this exact claim still owns the terminal transition.
        for field in ("payload", "run_after", "status", "attempts", "last_error", "locked_at", "locked_by"):
            set_committed_value(job, field, getattr(job, field))
        with db.no_autoflush:
            result = await db.execute(
                update(Job)
                .where(*claim)
                .values(**values)
                .returning(Job.id)
                .execution_options(synchronize_session=False)
            )
        if result.scalar_one_or_none() is None:
            await db.rollback()
            return False
        for field, value in values.items():
            set_committed_value(job, field, value)
        await db.commit()
        return True

    try:
        if job.kind == "recalculate_daily_load":
            await recompute_daily_load(
                db,
                int(job.payload["athlete_id"]),
                date.fromisoformat(job.payload["from_date"]),
            )
        elif job.kind == "send_resend_email":
            delivered = await send_queued_email(db, job)
            # Reducir retención de PII incluso cifrada tras la entrega.
            job.payload = {"delivered": delivered}
        elif job.kind == "intervals_sync":
            from app.services.intervals_real import execute_intervals_job

            await execute_intervals_job(db, job)
        elif job.kind == "intervals_disconnect":
            from app.services.intervals_real import execute_intervals_disconnect_job

            await execute_intervals_disconnect_job(db, job)
        elif job.kind == "product_notification":
            from app.services.product_notifications import dispatch_product_notification

            await dispatch_product_notification(db, job)
        elif await dispatch_privacy_job(db, job):
            pass
        else:
            raise ValueError(f"Tipo de trabajo no soportado: {job.kind}")
        if await finish(
            {"status": "completed", "payload": job.payload, "last_error": None, "locked_at": None, "locked_by": None}
        ):
            logger.info(json.dumps({"event": "job_completed", "kind": job_kind, "attempt": attempt}))
    except PushDeferred:
        await finish(
            {
                "status": "pending",
                "run_after": job.run_after,
                "attempts": max(0, attempt - 1),
                "locked_at": None,
                "locked_by": None,
            }
        )
    except Exception as exc:
        await db.rollback()
        job = await db.scalar(select(Job).where(*claim).execution_options(populate_existing=True))
        if job is None:
            return
        status = "dead" if attempt >= job.max_attempts else "pending"
        delay = settings.JOB_BACKOFF_BASE_SECONDS * (2 ** max(attempt - 1, 0))
        values = {
            "status": status,
            "last_error": "Tipo de trabajo no soportado" if job_kind == "unsupported" else type(exc).__name__,
            "locked_at": None,
            "locked_by": None,
            "run_after": datetime.now(UTC) + timedelta(seconds=delay),
        }
        if await finish(values):
            logger.warning(
                json.dumps(
                    {
                        "event": "job_failed",
                        "kind": job_kind,
                        "attempt": attempt,
                        "status": status,
                        "error_type": type(exc).__name__,
                    }
                )
            )


async def run_once(worker_id: str | None = None) -> int:
    worker_id = worker_id or f"{socket.gethostname()}:{os.getpid()}"
    async with async_session_maker() as db:
        from app.services.notification_scheduler import schedule_workout_reminders
        from app.services.privacy import schedule_retention

        await schedule_retention(db)
        await schedule_workout_reminders(db)
        heartbeat = await db.get(WorkerHeartbeat, worker_id)
        if heartbeat is None:
            db.add(WorkerHeartbeat(worker_id=worker_id, last_seen_at=datetime.now(UTC)))
        else:
            heartbeat.last_seen_at = datetime.now(UTC)
        await db.commit()
        await emit_worker_health(db)
        jobs = await claim_jobs(db, worker_id)
        claims = [(job.id, job.attempts) for job in jobs]
        renewer = asyncio.create_task(renew_claims(worker_id, claims)) if claims else None
        try:
            for job_id, attempt in claims:
                fresh = await db.scalar(
                    select(Job)
                    .where(
                        Job.id == job_id, Job.attempts == attempt, Job.status == "running", Job.locked_by == worker_id
                    )
                    .execution_options(populate_existing=True)
                )
                if fresh is not None:
                    await execute_job(db, fresh)
        finally:
            if renewer is not None:
                renewer.cancel()
                with suppress(asyncio.CancelledError):
                    await renewer
        return len(jobs)


async def renew_claims(worker_id: str, claims: list[tuple[int, int]]) -> None:
    while True:
        await asyncio.sleep(20)
        async with async_session_maker() as db:
            now = datetime.now(UTC)
            await db.execute(
                update(Job)
                .where(
                    or_(*(and_(Job.id == job_id, Job.attempts == attempt) for job_id, attempt in claims)),
                    Job.status == "running",
                    Job.locked_by == worker_id,
                )
                .values(locked_at=now)
            )
            await db.execute(
                update(WorkerHeartbeat).where(WorkerHeartbeat.worker_id == worker_id).values(last_seen_at=now)
            )
            await db.commit()
            await emit_worker_health(db)


async def emit_worker_health(db: AsyncSession) -> None:
    global last_health_emission
    if time.monotonic() - last_health_emission < 60:
        return
    now = datetime.now(UTC)
    counts = dict((await db.execute(select(Job.status, func.count()).group_by(Job.status))).all())
    oldest = await db.scalar(select(func.min(Job.run_after)).where(Job.status == "pending"))
    stale = await db.scalar(
        select(func.count()).select_from(Job).where(Job.status == "running", Job.locked_at < now - timedelta(minutes=5))
    )
    if oldest is not None and oldest.tzinfo is None:
        oldest = oldest.replace(tzinfo=UTC)
    logger.info(
        json.dumps(
            {
                "event": "worker_health",
                "pending_count": counts.get("pending", 0),
                "dead_count": counts.get("dead", 0),
                "oldest_pending_age_seconds": max(0, (now - oldest).total_seconds()) if oldest else 0,
                "stale_running_count": stale or 0,
            }
        )
    )
    last_health_emission = time.monotonic()


async def run_forever() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    while True:
        processed = await run_once()
        if processed == 0:
            await asyncio.sleep(settings.WORKER_POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(run_forever())
