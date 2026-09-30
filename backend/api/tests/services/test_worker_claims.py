"""Claims and outbox invariants on SQLite and an opt-in isolated PostgreSQL schema."""

import asyncio
import os
from contextlib import asynccontextmanager, suppress
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.models import Base, PasswordReset, User
from app.infrastructure.database.models.operations import WorkerHeartbeat
from app.infrastructure.database.models.product import DailyLoad, Job
from app.services import email, jobs
from app.services.notifications import PushDeferred


@asynccontextmanager
async def database(backend):
    admin = None
    schema = None
    if backend == "postgres":
        url = os.environ.get("NODO_WORKER_TEST_DATABASE_URL")
        if not url:
            pytest.skip("NODO_WORKER_TEST_DATABASE_URL required for isolated PostgreSQL claims")
        parsed = make_url(url)
        if parsed.host not in {"localhost", "127.0.0.1", "postgres"}:
            raise ValueError("Worker tests require a local synthetic PostgreSQL database")
        schema = f"worker_claims_{uuid4().hex}"
        admin = create_async_engine(url)
        async with admin.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
    else:
        engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            user = User(
                email="qa-worker-claims@example.com",
                hashed_password="synthetic-only",
                first_name="QA",
                last_name="Worker",
                timezone="UTC",
            )
            db.add(user)
            await db.commit()
            user_id = user.id
        yield sessions, user_id
    finally:
        await engine.dispose()
        if admin is not None:
            async with admin.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            await admin.dispose()


async def new_claim(sessions):
    async with sessions() as db:
        row = Job(
            kind="send_resend_email",
            payload={"ciphertext": "synthetic"},
            run_after=datetime.now(UTC),
            max_attempts=2,
        )
        db.add(row)
        await db.commit()
        return next(item for item in await jobs.claim_jobs(db, "review-owner") if item.id == row.id)


@pytest.mark.parametrize("backend", ["sqlite", "postgres"])
@pytest.mark.parametrize("outcome", ["complete", "defer", "retry"])
def test_lost_claim_rolls_back_handler_and_cannot_change_replacement(backend, outcome, monkeypatch):
    async def scenario():
        async with database(backend) as (sessions, user_id):
            claim = await new_claim(sessions)

            async def dispatch(db, row):
                db.add(
                    DailyLoad(
                        athlete_id=user_id,
                        local_date=date(2026, 9, 30),
                        load_unit="trimp",
                        load_value=3,
                        ctl=1,
                        atl=1,
                        tsb=0,
                        formula_version="review",
                        recomputed_at=datetime.now(UTC),
                    )
                )
                async with sessions() as other:
                    await other.execute(update(Job).where(Job.id == row.id).values(locked_by="replacement", attempts=2))
                    await other.commit()
                if outcome == "defer":
                    row.run_after = datetime.now(UTC) + timedelta(hours=1)
                    raise PushDeferred()
                if outcome == "retry":
                    raise RuntimeError("synthetic provider failure")
                return True

            monkeypatch.setattr(jobs, "send_queued_email", dispatch)
            async with sessions() as db:
                await jobs.execute_job(db, claim)
            async with sessions() as db:
                fresh = await db.get(Job, claim.id)
                assert (fresh.status, fresh.locked_by, fresh.attempts, fresh.payload) == (
                    "running",
                    "replacement",
                    2,
                    {"ciphertext": "synthetic"},
                )
                assert await db.scalar(select(DailyLoad.id)) is None

    asyncio.run(scenario())


@pytest.mark.parametrize("backend", ["sqlite", "postgres"])
def test_quiet_deferred_claim_does_not_consume_attempt(backend, monkeypatch):
    async def scenario():
        async with database(backend) as (sessions, _):
            claim = await new_claim(sessions)

            async def deferred(db, row):
                row.run_after = datetime.now(UTC) + timedelta(hours=1)
                raise PushDeferred()

            monkeypatch.setattr(jobs, "send_queued_email", deferred)
            async with sessions() as db:
                await jobs.execute_job(db, claim)
            async with sessions() as db:
                fresh = await db.get(Job, claim.id)
                future = fresh.run_after if fresh.run_after.tzinfo else fresh.run_after.replace(tzinfo=UTC)
                assert fresh.status == "pending" and fresh.attempts == 0 and future > datetime.now(UTC)
                assert fresh.locked_by is None and fresh.locked_at is None

    asyncio.run(scenario())


@pytest.mark.parametrize("backend", ["sqlite", "postgres"])
def test_provider_failure_uses_backoff_then_dead(backend, monkeypatch):
    async def scenario():
        async with database(backend) as (sessions, _):
            claim = await new_claim(sessions)

            async def failed(db, row):
                raise RuntimeError("synthetic")

            monkeypatch.setattr(jobs, "send_queued_email", failed)
            for expected in ("pending", "dead"):
                async with sessions() as db:
                    if expected == "dead":
                        claim = next(row for row in await jobs.claim_jobs(db, "review-owner") if row.id == claim.id)
                    await jobs.execute_job(db, claim)
                    fresh = await db.get(Job, claim.id)
                    assert fresh.status == expected and fresh.last_error == "RuntimeError"
                    assert fresh.locked_by is None and fresh.locked_at is None
                    future = fresh.run_after if fresh.run_after.tzinfo else fresh.run_after.replace(tzinfo=UTC)
                    assert future > datetime.now(UTC)
                    if expected == "pending":
                        fresh.run_after = datetime.now(UTC)
                        await db.commit()

    asyncio.run(scenario())


@pytest.mark.parametrize("backend", ["sqlite", "postgres"])
def test_renew_exact_claim_and_heartbeat_prevents_reclaim(backend, monkeypatch):
    async def scenario():
        async with database(backend) as (sessions, _):
            lease = await new_claim(sessions)
            replacement = await new_claim(sessions)
            stale = datetime.now(UTC) - timedelta(minutes=6)
            async with sessions() as db:
                await db.execute(update(Job).where(Job.id == lease.id).values(locked_at=stale))
                await db.execute(
                    update(Job)
                    .where(Job.id == replacement.id)
                    .values(locked_at=stale, locked_by="replacement", attempts=2)
                )
                db.add(WorkerHeartbeat(worker_id="review-owner", last_seen_at=stale))
                await db.commit()
            renewed = asyncio.Event()
            original_sleep = asyncio.sleep
            ticks = 0

            async def quick_sleep(seconds):
                nonlocal ticks
                ticks += 1
                if ticks > 1:
                    renewed.set()
                    await asyncio.Future()
                await original_sleep(0.01)

            monkeypatch.setattr(jobs, "async_session_maker", sessions)
            monkeypatch.setattr(jobs, "asyncio", SimpleNamespace(sleep=quick_sleep))
            task = asyncio.create_task(
                jobs.renew_claims("review-owner", [(lease.id, lease.attempts), (replacement.id, replacement.attempts)])
            )
            try:
                await asyncio.wait_for(renewed.wait(), 3)
            finally:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
            async with sessions() as db:
                fresh = await db.get(Job, lease.id)
                heartbeat = await db.get(WorkerHeartbeat, "review-owner")
                locked_at = fresh.locked_at if fresh.locked_at.tzinfo else fresh.locked_at.replace(tzinfo=UTC)
                seen_at = (
                    heartbeat.last_seen_at
                    if heartbeat.last_seen_at.tzinfo
                    else heartbeat.last_seen_at.replace(tzinfo=UTC)
                )
                assert locked_at > stale and seen_at > stale
                other = await db.get(Job, replacement.id)
                other_time = other.locked_at if other.locked_at.tzinfo else other.locked_at.replace(tzinfo=UTC)
                assert other.locked_by == "replacement" and other.attempts == 2 and other_time == stale
                assert not any(row.id == lease.id for row in await jobs.claim_jobs(db, "challenger"))

    asyncio.run(scenario())


@pytest.mark.parametrize("backend", ["sqlite", "postgres"])
@pytest.mark.parametrize("reason", ["deleted", "consumed", "expired", "missing_token"])
def test_email_invalid_owner_or_token_skips_provider(backend, reason, monkeypatch):
    async def scenario():
        async with database(backend) as (sessions, user_id):
            async with sessions() as db:
                token = PasswordReset(
                    user_id=user_id, token_hash="a" * 64, expires_at=datetime.now(UTC) + timedelta(hours=1)
                )
                db.add(token)
                await db.flush()
                mail = Job(
                    kind="send_resend_email",
                    payload={"ciphertext": "synthetic"},
                    run_after=datetime.now(UTC),
                    dedupe_key=f"nodo-password-reset-{token.id}",
                )
                db.add(mail)
                user = await db.get(User, user_id)
                if reason == "deleted":
                    user.deleted_at = datetime.now(UTC)
                elif reason == "consumed":
                    token.consumed_at = datetime.now(UTC)
                elif reason == "expired":
                    token.expires_at = datetime.now(UTC) - timedelta(hours=1)
                else:
                    await db.delete(token)
                await db.commit()

                def forbidden():
                    raise AssertionError("Invalid outbox must not attempt provider/configuration")

                monkeypatch.setattr(email, "email_ready", forbidden)
                assert await email.send_queued_email(db, mail) is False

    asyncio.run(scenario())
