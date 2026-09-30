import asyncio
from datetime import UTC, date, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.infrastructure.database.models import Activity, Base, User
from app.infrastructure.database.models.product import DailyLoad, Job
from app.infrastructure.database.models.user import UserRole
from app.services import jobs as worker
from app.services.jobs import execute_job, recompute_daily_load


def test_recompute_daily_load_includes_rest_days():
    async def scenario():
        engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            athlete = User(
                email="load@nodo.com",
                hashed_password=hash_password("A-long-local-password"),
                first_name="Load",
                last_name="Test",
                timezone="UTC",
                role=UserRole.ATHLETE,
            )
            db.add(athlete)
            await db.flush()
            db.add_all(
                [
                    Activity(
                        athlete_id=athlete.id,
                        file_name="one.fit",
                        file_hash="1" * 64,
                        provider="manual_fit",
                        sport_type="running",
                        timezone="UTC",
                        start_time=datetime(2026, 9, 1, tzinfo=UTC),
                        calculated_trimp=50,
                    ),
                    Activity(
                        athlete_id=athlete.id,
                        file_name="two.fit",
                        file_hash="2" * 64,
                        provider="manual_fit",
                        sport_type="running",
                        timezone="UTC",
                        start_time=datetime(2026, 9, 3, tzinfo=UTC),
                        calculated_trimp=30,
                    ),
                ]
            )
            await db.commit()
            await recompute_daily_load(db, athlete.id, date(2026, 9, 1))
            await db.commit()
            rows = (
                await db.scalars(
                    select(DailyLoad).where(DailyLoad.athlete_id == athlete.id).order_by(DailyLoad.local_date)
                )
            ).all()
            assert [row.local_date for row in rows[:3]] == [
                date(2026, 9, 1),
                date(2026, 9, 2),
                date(2026, 9, 3),
            ]
            assert rows[1].load_value == 0
            assert rows[-1].local_date == datetime.now(UTC).date()
            assert rows[-1].ctl < rows[2].ctl
        await engine.dispose()

    asyncio.run(scenario())


def test_job_failure_retries_then_enters_dead_letter():
    async def scenario():
        engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            job = Job(
                kind="unsupported",
                payload={},
                run_after=datetime.now(UTC),
                attempts=2,
                max_attempts=2,
                status="running",
            )
            db.add(job)
            await db.commit()
            await execute_job(db, job)
            refreshed = await db.get(Job, job.id)
            assert refreshed.status == "dead"
            assert "no soportado" in refreshed.last_error
        await engine.dispose()

    asyncio.run(scenario())


def test_claimed_batch_does_not_send_deleted_second_job(monkeypatch):
    async def scenario():
        engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        calls = []
        async with sessions() as db:
            db.add_all(
                [
                    Job(
                        kind="send_resend_email",
                        payload={"ciphertext": "synthetic"},
                        run_after=datetime.now(UTC),
                        max_attempts=3,
                    )
                    for _ in range(2)
                ]
            )
            await db.commit()
            claimed = await worker.claim_jobs(db, "first-worker")
            assert len(claimed) == 2
            first_id, second_id = claimed[0].id, claimed[1].id

            async def send(session, job):
                calls.append(job.id)
                async with sessions() as other:
                    await other.execute(delete(Job).where(Job.id == second_id))
                    await other.commit()
                return True

            monkeypatch.setattr(worker, "send_queued_email", send)
            await execute_job(db, claimed[0])
            await execute_job(db, claimed[1])
            assert calls == [first_id]
            assert (await db.get(Job, first_id)).status == "completed"
        await engine.dispose()

    asyncio.run(scenario())


def test_old_worker_cannot_finish_a_claim_recovered_by_another_worker(monkeypatch):
    async def scenario():
        engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            row = Job(
                kind="send_resend_email",
                payload={"ciphertext": "synthetic"},
                run_after=datetime.now(UTC),
                max_attempts=3,
            )
            db.add(row)
            await db.commit()
            claim = (await worker.claim_jobs(db, "old-worker"))[0]
            identifier = claim.id

            async def send(session, job):
                async with sessions() as other:
                    await other.execute(
                        update(Job).where(Job.id == identifier).values(locked_by="new-worker", attempts=2)
                    )
                    await other.commit()
                return True

            monkeypatch.setattr(worker, "send_queued_email", send)
            await execute_job(db, claim)
            fresh = await db.scalar(select(Job).where(Job.id == identifier).execution_options(populate_existing=True))
            assert fresh.status == "running" and fresh.locked_by == "new-worker" and fresh.attempts == 2
            assert fresh.payload == {"ciphertext": "synthetic"}
        await engine.dispose()

    asyncio.run(scenario())
