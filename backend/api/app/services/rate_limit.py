import hashlib
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.product import AuthRateLimit

WINDOW = timedelta(minutes=15)
MAX_FAILURES = 5


def _hash(namespace: str, key: str) -> str:
    return hashlib.sha256(f"{namespace}:{key.lower()}".encode()).hexdigest()


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


async def enforce_auth_rate_limit(db: AsyncSession, namespace: str, key: str) -> None:
    record = await db.scalar(
        select(AuthRateLimit).where(AuthRateLimit.key_hash == _hash(namespace, key)).with_for_update()
    )
    if record and record.blocked_until and _aware(record.blocked_until) > datetime.now(UTC):
        raise HTTPException(429, "Demasiados intentos; inténtalo más tarde")


async def register_auth_failure(db: AsyncSession, namespace: str, key: str) -> None:
    digest = _hash(namespace, key)
    now = datetime.now(UTC)
    record = await db.scalar(select(AuthRateLimit).where(AuthRateLimit.key_hash == digest).with_for_update())
    if record is None:
        record = AuthRateLimit(key_hash=digest, failures=1, window_started_at=now)
        db.add(record)
    elif now - _aware(record.window_started_at) > WINDOW:
        record.failures = 1
        record.window_started_at = now
        record.blocked_until = None
    else:
        record.failures += 1
    if record.failures >= MAX_FAILURES:
        record.blocked_until = now + WINDOW
    await db.commit()


async def clear_auth_failures(db: AsyncSession, namespace: str, key: str) -> None:
    await db.execute(delete(AuthRateLimit).where(AuthRateLimit.key_hash == _hash(namespace, key)))
