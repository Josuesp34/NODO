import asyncio
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import func, select, update
from test_privacy_notifications import enable_push, run
from test_privacy_notifications import private_api as _private_api

from app.core.config import settings
from app.infrastructure.database.models import User
from app.infrastructure.database.models.privacy import NotificationDelivery
from app.infrastructure.database.models.product import AthleteConnection, Consent, Job
from app.services import intervals_real, jobs
from app.services.product_notifications import dispatch_product_notification


@pytest.fixture(params=["sqlite", "postgres"])
def private_api(request, monkeypatch):
    yield from _private_api.__wrapped__(request, monkeypatch)


@pytest.fixture
def sync_api(private_api, monkeypatch):
    api = private_api
    monkeypatch.setattr(settings, "PROVIDER_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    for index in (0, 1):
        enable_push(api, index)
        response = api.client.put(
            "/api/v1/notification-preferences",
            headers=api.identities[index][1],
            json={"enabled": True, "categories": ["sync"], "timezone": "UTC"},
        )
        assert response.status_code == 200
    return api


async def seed_sync(api, *, max_attempts=1):
    athlete_id = api.identities[1][0]
    token_enc = intervals_real.cipher().encrypt(b"synthetic-provider-token").decode()
    async with api.sessions() as db:
        connection = AthleteConnection(
            athlete_id=athlete_id,
            provider=intervals_real.PROVIDER,
            external_athlete_id="synthetic-remote",
            status="connected",
            access_token_enc=token_enc,
        )
        job = Job(
            kind="intervals_sync",
            payload={"athlete_id": athlete_id, "backfill": False},
            dedupe_key="synthetic-terminal-sync",
            status="running",
            attempts=1,
            max_attempts=max_attempts,
            locked_by="synthetic-worker",
            locked_at=datetime.now(UTC),
            run_after=datetime.now(UTC),
        )
        db.add_all([connection, job])
        await db.commit()
        return connection.id, job.id, token_enc


def install_503(monkeypatch, *, before_failure=None):
    calls = []

    async def unavailable(request):
        calls.append(request.url.path)
        if len(calls) == 1 and before_failure:
            await before_failure()
        return httpx.Response(503, json={"untrusted": "synthetic-private-response"})

    transport = httpx.MockTransport(unavailable)

    def initialize(self, transport_override=None):
        self.transport = transport_override or transport

    monkeypatch.setattr(intervals_real.RealIntervalsAdapter, "__init__", initialize)
    return calls


def test_terminal_503_sets_error_and_fanout_once_without_persisting_provenance(sync_api, monkeypatch, caplog):
    api = sync_api
    calls = install_503(monkeypatch)

    async def scenario():
        connection_id, job_id, token_enc = await seed_sync(api)
        async with api.sessions() as db:
            job = await db.get(Job, job_id)
            await jobs.execute_job(db, job)
            await db.refresh(job)
            assert job.status == "dead" and job.last_error == "IntervalsError"
            assert job.payload == {"athlete_id": api.identities[1][0], "backfill": False}
            connection = await db.get(AthleteConnection, connection_id)
            assert connection.status == "error" and connection.access_token_enc == token_enc
            events = (await db.scalars(select(Job).where(Job.kind == "product_notification"))).all()
            assert len(events) == 2
            assert {event.payload["recipient_id"] for event in events} == {api.identities[0][0], api.identities[1][0]}
            assert all(event.payload["event_key"] == f"sync-problem:{connection_id}:{job_id}" for event in events)
            assert "synthetic-provider-token" not in json.dumps([event.payload for event in events])
            assert token_enc not in json.dumps([event.payload for event in events])
            assert "token_digest" not in json.dumps([event.payload for event in events])
            # Replaying a terminal job never calls the provider or creates another event.
            await jobs.execute_job(db, job)
            assert len(calls) == 3
            events = (await db.scalars(select(Job).where(Job.kind == "product_notification"))).all()
            for event in events:
                await dispatch_product_notification(db, event)
            await db.commit()
            deliveries = (await db.scalars(select(NotificationDelivery))).all()
            assert len(deliveries) == 2
            assert all(delivery.category == "sync" for delivery in deliveries)
            assert len({delivery.user_id for delivery in deliveries}) == 2

    run(scenario())
    assert "synthetic-provider-token" not in caplog.text
    assert "synthetic-private-response" not in caplog.text


def test_retriable_failure_does_not_mark_error_until_final_attempt(sync_api, monkeypatch):
    api = sync_api
    calls = install_503(monkeypatch)

    async def scenario():
        connection_id, job_id, _ = await seed_sync(api, max_attempts=2)
        async with api.sessions() as db:
            job = await db.get(Job, job_id)
            await jobs.execute_job(db, job)
            await db.refresh(job)
            assert job.status == "pending"
            assert (await db.get(AthleteConnection, connection_id)).status == "connected"
            assert await db.scalar(select(func.count()).select_from(Job).where(Job.kind == "product_notification")) == 0
            job.status, job.attempts, job.locked_by, job.locked_at = "running", 2, "synthetic-worker", datetime.now(UTC)
            await db.commit()
            await jobs.execute_job(db, job)
            assert (await db.get(AthleteConnection, connection_id)).status == "error"
            await db.refresh(job)
            assert job.status == "dead" and len(calls) == 6
            assert await db.scalar(select(func.count()).select_from(Job).where(Job.kind == "product_notification")) == 2

    run(scenario())


@pytest.mark.parametrize(
    "change", ["new_token", "replaced_connection", "withdrawal", "deleted_user", "newer_sync", "reconnect_required"]
)
def test_terminal_error_cannot_overwrite_new_authorization_or_sync(sync_api, monkeypatch, change):
    api = sync_api

    async def scenario():
        connection_id, job_id, token_enc = await seed_sync(api)
        replacement_id = connection_id + 100

        async def changed_while_http_runs():
            async with api.sessions() as other:
                connection = await other.get(AthleteConnection, connection_id)
                if change == "new_token":
                    connection.access_token_enc = (
                        intervals_real.cipher().encrypt(b"synthetic-reconnected-token").decode()
                    )
                elif change == "replaced_connection":
                    await other.delete(connection)
                    await other.flush()
                    other.add(
                        AthleteConnection(
                            id=replacement_id,
                            athlete_id=api.identities[1][0],
                            provider=intervals_real.PROVIDER,
                            external_athlete_id="synthetic-new-remote",
                            status="connected",
                            access_token_enc=token_enc,
                        )
                    )
                elif change == "withdrawal":
                    other.add(
                        Consent(
                            user_id=api.identities[1][0],
                            scope="training_data_processing",
                            version="pilot-v1",
                            granted_at=datetime.now(UTC),
                            revoked_at=datetime.now(UTC),
                        )
                    )
                elif change == "deleted_user":
                    (await other.get(User, api.identities[1][0])).deleted_at = datetime.now(UTC)
                elif change == "newer_sync":
                    connection.last_sync_at = datetime.now(UTC) + timedelta(seconds=1)
                else:
                    connection.status = "reconnect_required"
                await other.commit()

        install_503(monkeypatch, before_failure=changed_while_http_runs)
        async with api.sessions() as db:
            job = await db.get(Job, job_id)
            await jobs.execute_job(db, job)
            await db.refresh(job)
            assert job.status == "dead"
            connection = await db.get(
                AthleteConnection, replacement_id if change == "replaced_connection" else connection_id
            )
            assert connection.status == ("reconnect_required" if change == "reconnect_required" else "connected")
            assert await db.scalar(select(func.count()).select_from(Job).where(Job.kind == "product_notification")) == 0

    run(scenario())


def test_lost_claim_rolls_back_terminal_connection_and_notice_changes(sync_api, monkeypatch):
    api = sync_api
    if api.sessions.kw["bind"].dialect.name != "postgresql":
        pytest.skip("Concurrent claim ownership requires independent PostgreSQL transactions")
    install_503(monkeypatch)
    original = intervals_real.mark_terminal_sync_failure

    async def mark_then_reclaim(db, job, error):
        assert await original(db, job, error)
        async with api.sessions() as other:
            await other.execute(update(Job).where(Job.id == job.id).values(locked_by="new-worker", attempts=2))
            await other.commit()
        return True

    monkeypatch.setattr(intervals_real, "mark_terminal_sync_failure", mark_then_reclaim)

    async def scenario():
        connection_id, job_id, token_enc = await seed_sync(api)
        async with api.sessions() as db:
            await asyncio.wait_for(jobs.execute_job(db, await db.get(Job, job_id)), timeout=10)
            connection = await db.get(AthleteConnection, connection_id)
            assert connection.status == "connected" and connection.access_token_enc == token_enc
            job = await db.get(Job, job_id)
            assert job.status == "running" and job.locked_by == "new-worker" and job.attempts == 2
            assert await db.scalar(select(func.count()).select_from(Job).where(Job.kind == "product_notification")) == 0

    run(scenario())
