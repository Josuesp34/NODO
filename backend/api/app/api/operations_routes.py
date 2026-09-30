from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import current_superuser
from app.core.config import settings
from app.core.database import get_db
from app.infrastructure.database.models import User
from app.infrastructure.database.models.operations import WorkerHeartbeat
from app.infrastructure.database.models.product import Job

router = APIRouter(prefix="/admin/operations", tags=["Operations"])


@router.get("")
async def operations(admin: User = Depends(current_superuser), db: AsyncSession = Depends(get_db)):
    now = datetime.now(UTC)
    grouped = (await db.execute(select(Job.kind, Job.status, func.count()).group_by(Job.kind, Job.status))).all()
    last_seen = await db.scalar(select(func.max(WorkerHeartbeat.last_seen_at)))
    oldest = await db.scalar(select(func.min(Job.run_after)).where(Job.status == "pending"))
    running_stale = await db.scalar(
        select(func.count()).select_from(Job).where(Job.status == "running", Job.locked_at < now - timedelta(minutes=5))
    )
    if last_seen is not None and last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=UTC)
    if oldest is not None and oldest.tzinfo is None:
        oldest = oldest.replace(tzinfo=UTC)
    return {
        "observed_at": now,
        "worker_last_seen_at": last_seen,
        "worker_recent": (
            last_seen is not None
            and (now - last_seen).total_seconds() < max(60, 3 * settings.WORKER_POLL_INTERVAL_SECONDS)
        ),
        "queue": [{"kind": kind, "status": status, "count": count} for kind, status, count in grouped],
        "oldest_pending_age_seconds": max(0, (now - oldest).total_seconds()) if oldest else None,
        "stale_running_count": running_stale,
        "provider_verification": "consultar evidencia de activación; configuración no acredita disponibilidad",
    }
