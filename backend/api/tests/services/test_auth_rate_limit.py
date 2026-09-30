"""Local isolated databases; authentication requests never contact an external service."""

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api import auth_routes
from app.core.database import get_db
from app.core.security import token_hash
from app.infrastructure.database.models import AuthSession, Base, User
from app.infrastructure.database.models.product import AuthRateLimit
from app.services import rate_limit


@asynccontextmanager
async def database(backend):
    admin = None
    schema = None
    if backend == "postgres":
        url = (
            os.environ.get("NODO_RATE_LIMIT_TEST_DATABASE_URL")
            or os.environ.get("NODO_WORKER_TEST_DATABASE_URL")
            or os.environ.get("NODO_PRIVACY_TEST_DATABASE_URL")
        )
        if not url:
            pytest.skip("Local PostgreSQL test URL required for the isolated rate-limit tests")
        if make_url(url).host not in {"localhost", "127.0.0.1", "postgres"}:
            raise ValueError("Rate-limit tests require a local synthetic database")
        schema = f"auth_rate_test_{uuid4().hex}"
        admin = create_async_engine(url)
        async with admin.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
    else:
        engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(
                lambda sync: Base.metadata.create_all(
                    sync, tables=[User.__table__, AuthSession.__table__, AuthRateLimit.__table__]
                )
            )
        yield sessions
    finally:
        await engine.dispose()
        if admin is not None:
            async with admin.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            await admin.dispose()


def freeze_clock(monkeypatch, instant):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)

    monkeypatch.setattr(rate_limit, "datetime", Clock)


@pytest.mark.parametrize("backend", ["sqlite", "postgres"])
def test_fifth_failure_blocks_and_success_clears_only_its_namespace(backend, monkeypatch):
    now = datetime(2026, 9, 30, 12, tzinfo=UTC)
    freeze_clock(monkeypatch, now)

    async def scenario():
        async with database(backend) as sessions:
            for number in range(1, rate_limit.MAX_FAILURES + 1):
                async with sessions() as db:
                    await rate_limit.enforce_auth_rate_limit(db, "login", "Synthetic@Example.com")
                    await rate_limit.register_auth_failure(db, "login", "synthetic@example.com")
                async with sessions() as db:
                    record = await db.scalar(select(AuthRateLimit))
                    assert record.failures == number
                    assert rate_limit._aware(record.window_started_at) == now
                    assert (record.blocked_until is not None) == (number >= rate_limit.MAX_FAILURES)
            async with sessions() as db:
                with pytest.raises(HTTPException) as blocked:
                    await rate_limit.enforce_auth_rate_limit(db, "login", "SYNTHETIC@example.com")
                assert blocked.value.status_code == 429
                record = await db.scalar(select(AuthRateLimit))
                assert rate_limit._aware(record.blocked_until) == now + rate_limit.WINDOW
                await rate_limit.register_auth_failure(db, "refresh", "synthetic@example.com")
                await rate_limit.clear_auth_failures(db, "login", "Synthetic@example.com")
                await db.commit()
            async with sessions() as db:
                await rate_limit.enforce_auth_rate_limit(db, "login", "synthetic@example.com")
                records = (await db.scalars(select(AuthRateLimit))).all()
                assert len(records) == 1
                assert records[0].key_hash == rate_limit._hash("refresh", "synthetic@example.com")
                assert records[0].failures == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("backend", ["sqlite", "postgres"])
@pytest.mark.parametrize("past_boundary", [False, True])
def test_window_resets_only_after_fifteen_minutes(backend, past_boundary, monkeypatch):
    now = datetime(2026, 9, 30, 12, tzinfo=UTC)
    freeze_clock(monkeypatch, now)
    started = now - rate_limit.WINDOW - (timedelta(microseconds=1) if past_boundary else timedelta())

    async def scenario():
        async with database(backend) as sessions:
            async with sessions() as db:
                db.add(
                    AuthRateLimit(
                        key_hash=rate_limit._hash("refresh", "synthetic"),
                        failures=rate_limit.MAX_FAILURES,
                        window_started_at=started,
                        blocked_until=now,
                    )
                )
                await db.commit()
                await rate_limit.enforce_auth_rate_limit(db, "refresh", "synthetic")
                await rate_limit.register_auth_failure(db, "refresh", "synthetic")
            async with sessions() as db:
                record = await db.scalar(select(AuthRateLimit))
                assert record.failures == (1 if past_boundary else rate_limit.MAX_FAILURES + 1)
                assert rate_limit._aware(record.window_started_at) == (now if past_boundary else started)
                if past_boundary:
                    assert record.blocked_until is None
                    await rate_limit.enforce_auth_rate_limit(db, "refresh", "synthetic")
                else:
                    assert rate_limit._aware(record.blocked_until) == now + rate_limit.WINDOW
                    with pytest.raises(HTTPException) as blocked:
                        await rate_limit.enforce_auth_rate_limit(db, "refresh", "synthetic")
                    assert blocked.value.status_code == 429

    asyncio.run(scenario())


def test_concurrent_invalid_refresh_initially_missing_has_no_500_or_lost_failures(monkeypatch):
    now = datetime(2026, 9, 30, 12, tzinfo=UTC)
    freeze_clock(monkeypatch, now)
    concurrency = rate_limit.MAX_FAILURES + 3
    synthetic_token = "nodo-synthetic-invalid-refresh-token"

    async def scenario():
        async with database("postgres") as sessions:
            app = FastAPI()
            app.include_router(auth_routes.router, prefix="/api/v1")

            async def session_dependency():
                async with sessions() as db:
                    yield db

            app.dependency_overrides[get_db] = session_dependency
            ready = asyncio.Event()
            arrivals = 0

            async def enforce_before_insert(db, namespace, key):
                nonlocal arrivals
                await rate_limit.enforce_auth_rate_limit(db, namespace, key)
                arrivals += 1
                if arrivals == concurrency:
                    ready.set()
                await asyncio.wait_for(ready.wait(), timeout=10)

            monkeypatch.setattr(auth_routes, "enforce_auth_rate_limit", enforce_before_insert)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://local.test"
            ) as client:
                responses = await asyncio.wait_for(
                    asyncio.gather(
                        *(
                            client.post("/api/v1/auth/refresh", json={"refresh_token": synthetic_token})
                            for _ in range(concurrency)
                        )
                    ),
                    timeout=20,
                )
                assert [response.status_code for response in responses] == [401] * concurrency
                blocked = await client.post("/api/v1/auth/refresh", json={"refresh_token": synthetic_token})
                assert blocked.status_code == 429
            async with sessions() as db:
                assert await db.scalar(select(func.count()).select_from(AuthRateLimit)) == 1
                record = await db.scalar(select(AuthRateLimit))
                assert record.key_hash == rate_limit._hash("refresh", token_hash(synthetic_token))
                assert record.failures == concurrency
                assert rate_limit._aware(record.blocked_until) == now + rate_limit.WINDOW

    asyncio.run(scenario())


def test_concurrent_expired_window_resets_once_and_counts_every_failure(monkeypatch):
    now = datetime(2026, 9, 30, 12, tzinfo=UTC)
    freeze_clock(monkeypatch, now)
    concurrency = rate_limit.MAX_FAILURES + 3

    async def scenario():
        async with database("postgres") as sessions:
            async with sessions() as db:
                db.add(
                    AuthRateLimit(
                        key_hash=rate_limit._hash("login", "synthetic"),
                        failures=42,
                        window_started_at=now - rate_limit.WINDOW - timedelta(seconds=1),
                        blocked_until=now - timedelta(seconds=1),
                    )
                )
                await db.commit()
            ready = asyncio.Event()

            async def fail():
                async with sessions() as db:
                    await ready.wait()
                    await rate_limit.register_auth_failure(db, "login", "synthetic")

            tasks = [asyncio.create_task(fail()) for _ in range(concurrency)]
            ready.set()
            await asyncio.wait_for(asyncio.gather(*tasks), timeout=20)
            async with sessions() as db:
                record = await db.scalar(select(AuthRateLimit))
                assert record.failures == concurrency
                assert rate_limit._aware(record.window_started_at) == now
                assert rate_limit._aware(record.blocked_until) == now + rate_limit.WINDOW
                with pytest.raises(HTTPException) as blocked:
                    await rate_limit.enforce_auth_rate_limit(db, "login", "synthetic")
                assert blocked.value.status_code == 429

    asyncio.run(scenario())
