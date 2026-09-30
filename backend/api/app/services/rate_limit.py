import hashlib
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import case, delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
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
    dialect = db.get_bind().dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        raise RuntimeError("Auth rate limits require PostgreSQL or SQLite")
    insert = pg_insert if dialect == "postgresql" else sqlite_insert
    expired = AuthRateLimit.window_started_at < now - WINDOW
    failures = case((expired, 1), else_=AuthRateLimit.failures + 1)
    # A missing row cannot be locked by SELECT FOR UPDATE. The unique-key
    # upsert serializes both its creation and increments against the stored row.
    await db.execute(
        insert(AuthRateLimit)
        .values(key_hash=digest, failures=1, window_started_at=now, blocked_until=None)
        .on_conflict_do_update(
            index_elements=[AuthRateLimit.key_hash],
            set_={
                "failures": failures,
                "window_started_at": case((expired, now), else_=AuthRateLimit.window_started_at),
                "blocked_until": case(
                    (failures >= MAX_FAILURES, now + WINDOW),
                    (expired, None),
                    else_=AuthRateLimit.blocked_until,
                ),
                # Upserts do not invoke SQLAlchemy's Python-side onupdate.
                "updated_at": now,
            },
        )
    )
    await db.commit()


async def clear_auth_failures(db: AsyncSession, namespace: str, key: str) -> None:
    await db.execute(delete(AuthRateLimit).where(AuthRateLimit.key_hash == _hash(namespace, key)))
