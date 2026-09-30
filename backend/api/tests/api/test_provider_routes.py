# ruff: noqa: F811
import asyncio
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select
from test_pilot_product import invite_and_activate, pilot_api, register_and_login  # noqa: F401

from app.api.intervals_routes import router
from app.core.config import settings
from app.core.database import get_db
from app.infrastructure.database.models.product import AthleteConnection, Job, Observation
from app.infrastructure.database.models.providers import ProviderRecord
from app.services.intervals_real import SCOPES, RealIntervalsAdapter, ingest_activity, ingest_wellness
from app.services.vertex_assistant import Generated, ModelAnswer


@pytest.fixture
def provider_api(pilot_api, monkeypatch):
    pilot_api.app.include_router(router, prefix="/api/v1")
    monkeypatch.setattr(settings, "INTERVALS_CLIENT_ID", "fixture-client")
    monkeypatch.setattr(settings, "INTERVALS_CLIENT_SECRET", "fixture-secret")
    monkeypatch.setattr(
        settings, "INTERVALS_REDIRECT_URI", "http://localhost:3000/athlete/connections/intervals/callback"
    )
    monkeypatch.setattr(settings, "PROVIDER_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "INTERVALS_WEBHOOK_SECRET", "fixture-webhook")
    return pilot_api


def scenario(client):
    coach = register_and_login(client)
    athlete, headers = invite_and_activate(client, coach)
    return coach, athlete, headers


def test_oauth_session_bound_single_use_and_encrypted(provider_api, monkeypatch):
    coach, athlete, headers = scenario(provider_api)
    start = provider_api.post(f"/api/v1/connections/intervals/{athlete['id']}/authorize", headers=headers)
    assert start.status_code == 200, start.text
    query = parse_qs(urlparse(start.json()["authorization_url"]).query)
    assert query["scope"] == [",".join(SCOPES)]
    calls = []

    async def exchange(self, code):
        calls.append(code)
        return {"access_token": "fixture-plaintext-token", "scope": ",".join(SCOPES), "athlete": {"id": "i123"}}

    monkeypatch.setattr(RealIntervalsAdapter, "exchange_code", exchange)
    payload = {"state": query["state"][0], "code": "fixture-code"}
    assert provider_api.post("/api/v1/connections/intervals/callback", headers=coach, json=payload).status_code == 400
    response = provider_api.post("/api/v1/connections/intervals/callback", headers=headers, json=payload)
    assert response.status_code == 200, response.text
    assert "fixture-plaintext-token" not in response.text
    assert provider_api.post("/api/v1/connections/intervals/callback", headers=headers, json=payload).status_code == 400
    assert len(calls) == 1

    async def inspect():
        async for db in provider_api.app.dependency_overrides[get_db]():
            connection = await db.scalar(select(AthleteConnection))
            assert connection.refresh_token_enc is None
            assert "fixture-plaintext-token" not in connection.access_token_enc
            assert (
                Fernet(settings.PROVIDER_TOKEN_ENCRYPTION_KEY.encode()).decrypt(connection.access_token_enc.encode())
                == b"fixture-plaintext-token"
            )
            job = await db.scalar(select(Job).where(Job.kind == "intervals_sync"))
            assert job.payload["backfill"] is True

    asyncio.run(inspect())


def test_webhook_body_secret_duplicate_and_no_processing(provider_api):
    _coach, athlete, _headers = scenario(provider_api)

    async def seed():
        async for db in provider_api.app.dependency_overrides[get_db]():
            db.add(
                AthleteConnection(
                    athlete_id=athlete["id"],
                    provider="intervals_icu",
                    external_athlete_id="i123",
                    status="connected",
                    scopes=list(SCOPES),
                )
            )
            await db.commit()

    asyncio.run(seed())
    payload = {
        "secret": "fixture-webhook",
        "events": [
            {
                "athlete_id": "i123",
                "type": "ACTIVITY_UPLOADED",
                "timestamp": "2026-09-30T00:00:00Z",
                "activity": {"id": "activity123", "source": "GARMIN_CONNECT"},
            }
        ],
    }
    assert (
        provider_api.post("/api/v1/connections/intervals/webhook", json={**payload, "secret": "wrong"}).status_code
        == 401
    )
    assert (
        provider_api.post("/api/v1/connections/intervals/webhook", json={**payload, "secret": "inválido🔒"}).status_code
        == 401
    )
    first = provider_api.post("/api/v1/connections/intervals/webhook", json=payload)
    assert first.json() == {"accepted": 1}
    assert provider_api.post("/api/v1/connections/intervals/webhook", json=payload).json() == {"accepted": 0}
    assert (
        provider_api.post("/api/v1/connections/intervals/webhook", content=b"x" * (1024 * 1024 + 1)).status_code == 413
    )

    async def inspect():
        async for db in provider_api.app.dependency_overrides[get_db]():
            jobs = (await db.scalars(select(Job).where(Job.kind == "intervals_sync"))).all()
            assert len(jobs) == 1
            assert "fixture-webhook" not in str(jobs[0].payload)
            assert not (await db.scalars(select(ProviderRecord))).all()

    asyncio.run(inspect())


def test_real_ingestion_idempotence_provenance_units_and_fit_preserved(provider_api):
    _, athlete, _ = scenario(provider_api)

    async def run():
        from app.infrastructure.database.models import Activity, User

        async for db in provider_api.app.dependency_overrides[get_db]():
            user = await db.get(User, athlete["id"])
            payload = {
                "id": "activity123",
                "source": "GARMIN_CONNECT",
                "type": "Run",
                "start_date": "2026-09-20T12:00:00Z",
                "timezone": "America/Mexico_City",
                "moving_time": 60,
                "distance": 1000,
                "icu_training_load": 10,
                "icu_intervals": [{"id": 1, "moving_time": 60, "distance": 1000}],
            }
            assert await ingest_activity(db, user, {**payload, "source": "STRAVA"}) is False
            assert await ingest_activity(db, user, {**payload, "source": None, "device_name": "Garmin"}) is False
            await ingest_activity(db, user, payload)
            await ingest_activity(db, user, payload)
            await ingest_wellness(
                db, user, {"id": "2026-09-20", "hrv": 45, "hrvSDNN": 30, "sleepSecs": 28800, "vo2max": 51}
            )
            await db.flush()
            await ingest_wellness(db, user, {"id": "2026-09-20", "hrvSDNN": 35})
            await db.commit()
            activities = (await db.scalars(select(Activity))).all()
            assert len(activities) == 1 and activities[0].calculated_trimp is None
            observations = (await db.scalars(select(Observation))).all()
            assert len(observations) == 1
            assert observations[0].method == "SDNN" and observations[0].unit == "ms" and observations[0].value == 35
            assert observations[0].quality == "partial"

    asyncio.run(run())


def test_assistant_repeated_message_no_duplicate_and_typed_cross_scope(pilot_api):
    _coach, athlete, headers = scenario(pilot_api)
    thread = pilot_api.post("/api/v1/assistant/threads", headers=headers, json={"role": "athlete"}).json()
    url = f"/api/v1/assistant/threads/{thread['id']}/messages"
    payload = {"content": "Mis datos", "request_key": "request-fixture-001"}
    first = pilot_api.post(url, headers=headers, json=payload)
    repeated = pilot_api.post(url, headers=headers, json=payload)
    assert first.status_code == 200, first.text
    assert repeated.json() == first.json()
    assert len(pilot_api.get(url, headers=headers).json()) == 2
    assert pilot_api.post(url, headers=headers, json={**payload, "content": "Cambió"}).status_code == 409
    assert (
        pilot_api.post(
            "/api/v1/assistant/tools/read?role=athlete", headers=headers, json={"tool": "profile", "athlete_id": 1}
        ).status_code
        == 404
    )
    assert (
        pilot_api.post(
            "/api/v1/assistant/tools/read?role=athlete",
            headers=headers,
            json={"tool": "publish", "athlete_id": athlete["id"]},
        ).status_code
        == 422
    )


def test_assistant_monthly_requests_aggregate_both_roles(pilot_api, monkeypatch):
    coach, _athlete, headers = scenario(pilot_api)
    monkeypatch.setattr(settings, "AI_ORG_MONTHLY_REQUESTS", 1)
    t1 = pilot_api.post("/api/v1/assistant/threads", headers=headers, json={"role": "athlete"}).json()
    t2 = pilot_api.post("/api/v1/assistant/threads", headers=coach, json={"role": "coach"}).json()
    assert (
        pilot_api.post(
            f"/api/v1/assistant/threads/{t1['id']}/messages", headers=headers, json={"content": "A"}
        ).status_code
        == 200
    )
    assert (
        pilot_api.post(
            f"/api/v1/assistant/threads/{t2['id']}/messages", headers=coach, json={"content": "B"}
        ).status_code
        == 429
    )


def test_vertex_unknown_citations_fail_without_answer_or_write(pilot_api, monkeypatch):
    _coach, _athlete, headers = scenario(pilot_api)
    thread = pilot_api.post("/api/v1/assistant/threads", headers=headers, json={"role": "athlete"}).json()
    for name, value in {
        "AI_PROVIDER": "vertex",
        "AI_MODEL": "fixture",
        "AI_GCP_PROJECT": "fixture",
        "AI_INPUT_USD_PER_MILLION": 1.0,
        "AI_OUTPUT_USD_PER_MILLION": 1.0,
        "AI_USER_MONTHLY_BUDGET_USD": 10.0,
        "AI_ORG_MONTHLY_BUDGET_USD": 10.0,
    }.items():
        monkeypatch.setattr(settings, name, value)

    async def generate(*args):
        return Generated(ModelAnswer(answer="Inventado", citation_keys=["profile:999:999"]), 10, 20)

    monkeypatch.setattr("app.services.assistant_runtime.VertexAssistant.generate", generate)
    url = f"/api/v1/assistant/threads/{thread['id']}/messages"
    result = pilot_api.post(url, headers=headers, json={"content": "consulta"})
    assert result.status_code == 503, result.text
    assert "INVALID_CITATIONS" in result.text
    assert len(pilot_api.get(url, headers=headers).json()) == 1


def test_stream_contains_run_and_validated_final(pilot_api):
    _, _athlete, headers = scenario(pilot_api)
    thread = pilot_api.post("/api/v1/assistant/threads", headers=headers, json={"role": "athlete"}).json()
    result = pilot_api.post(
        f"/api/v1/assistant/threads/{thread['id']}/messages/stream",
        headers=headers,
        json={"content": "consulta", "request_key": "stream-fixture-001"},
    )
    assert result.status_code == 200, result.text
    assert '"type": "run"' in result.text and '"type": "result"' in result.text
    assert result.headers["content-type"].startswith("text/event-stream")


def test_oauth_state_rejects_another_session_of_same_account(provider_api, monkeypatch):
    _, athlete, headers = scenario(provider_api)
    start = provider_api.post(f"/api/v1/connections/intervals/{athlete['id']}/authorize", headers=headers).json()
    state = parse_qs(urlparse(start["authorization_url"]).query)["state"][0]
    login = provider_api.post(
        "/api/v1/auth/login", json={"email": athlete["email"], "password": "A-second-long-password"}
    ).json()
    other = {"Authorization": f"Bearer {login['access_token']}"}
    calls = []

    async def exchange(self, code):
        calls.append(code)

    monkeypatch.setattr(RealIntervalsAdapter, "exchange_code", exchange)
    result = provider_api.post(
        "/api/v1/connections/intervals/callback", headers=other, json={"state": state, "code": "x"}
    )
    assert result.status_code == 400, result.text
    assert not calls


def test_oauth_denial_consumes_state_and_never_exchanges(provider_api, monkeypatch):
    _, athlete, headers = scenario(provider_api)
    start = provider_api.post(f"/api/v1/connections/intervals/{athlete['id']}/authorize", headers=headers).json()
    state = parse_qs(urlparse(start["authorization_url"]).query)["state"][0]
    calls = []

    async def exchange(self, code):
        calls.append(code)

    monkeypatch.setattr(RealIntervalsAdapter, "exchange_code", exchange)
    denied = provider_api.post(
        "/api/v1/connections/intervals/callback", headers=headers, json={"state": state, "error": "access_denied"}
    )
    assert denied.status_code == 400 and "AUTHORIZATION_DENIED" in denied.text
    retry = provider_api.post(
        "/api/v1/connections/intervals/callback", headers=headers, json={"state": state, "code": "x"}
    )
    assert retry.status_code == 400 and "STATE_EXPIRED_OR_USED" in retry.text
    assert not calls


def test_disconnect_failure_is_durable_stops_ingestion_and_preserves_fit(provider_api, monkeypatch):
    from app.services.intervals_real import IntervalsError

    _, athlete, headers = scenario(provider_api)
    encrypted = Fernet(settings.PROVIDER_TOKEN_ENCRYPTION_KEY.encode()).encrypt(b"fixture-provider-token").decode()

    async def seed():
        from app.infrastructure.database.models import Activity

        async for db in provider_api.app.dependency_overrides[get_db]():
            db.add(
                AthleteConnection(
                    athlete_id=athlete["id"],
                    provider="intervals_icu",
                    status="connected",
                    access_token_enc=encrypted,
                    external_athlete_id="i123",
                    scopes=list(SCOPES),
                )
            )
            db.add(
                Activity(
                    athlete_id=athlete["id"],
                    provider="manual_fit",
                    file_name="fixture.fit",
                    file_hash="f" * 64,
                    start_time=datetime.now(UTC),
                    total_duration_sec=30,
                    total_distance_m=100,
                )
            )
            await db.commit()

    asyncio.run(seed())

    async def fail(self, token):
        raise IntervalsError("INTERVALS_TEMPORARILY_UNAVAILABLE", 503)

    monkeypatch.setattr(RealIntervalsAdapter, "disconnect", fail)
    response = provider_api.delete(f"/api/v1/connections/intervals/{athlete['id']}", headers=headers)
    assert response.status_code == 503, response.text
    status = provider_api.get(f"/api/v1/connections/intervals/{athlete['id']}", headers=headers).json()
    assert status["status"] == "disconnect_pending" and status["manual_fit_available"]

    async def inspect():
        from app.infrastructure.database.models import Activity

        async for db in provider_api.app.dependency_overrides[get_db]():
            assert (await db.scalar(select(Activity))).provider == "manual_fit"
            job = await db.scalar(select(Job).where(Job.kind == "intervals_disconnect"))
            assert job.payload == {"token_enc": encrypted}

    asyncio.run(inspect())


def test_sync_backfill_90_days_retries_are_idempotent_and_no_calendar_publish(provider_api, monkeypatch):
    from app.services.intervals_real import execute_intervals_job

    _, athlete, _headers = scenario(provider_api)
    windows = []

    async def window(self, token, remote, start, end):
        windows.append((start, end))
        return {
            "activity": [],
            "wellness": [{"id": str(start), "sleepSecs": 28800}],
            "calendar": [{"id": 123, "start_date_local": str(start), "name": "External draft"}],
        }

    monkeypatch.setattr(RealIntervalsAdapter, "window", window)

    async def run():
        from app.infrastructure.database.models import PrescribedWorkout

        async for db in provider_api.app.dependency_overrides[get_db]():
            db.add(
                AthleteConnection(
                    athlete_id=athlete["id"],
                    provider="intervals_icu",
                    status="connected",
                    access_token_enc=Fernet(settings.PROVIDER_TOKEN_ENCRYPTION_KEY.encode())
                    .encrypt(b"fixture")
                    .decode(),
                    external_athlete_id="i123",
                    scopes=list(SCOPES),
                )
            )
            job = Job(
                kind="intervals_sync",
                payload={"athlete_id": athlete["id"], "backfill": True},
                run_after=datetime.now(UTC),
                dedupe_key="fixture-backfill",
            )
            db.add(job)
            await db.commit()
            await execute_intervals_job(db, job)
            await db.commit()
            first = (await db.scalars(select(Observation))).all()
            await execute_intervals_job(db, job)
            await db.commit()
            second = (await db.scalars(select(Observation))).all()
            assert len(first) == len(second) == 13
            assert not (await db.scalars(select(PrescribedWorkout))).all()
            scheduled = (await db.scalars(select(Job).where(Job.dedupe_key.like("intervals:scheduled:%")))).all()
            assert len(scheduled) == 1

    asyncio.run(run())
    assert len(windows) == 26 and (windows[12][1] - windows[0][0]).days == 90
    assert all((end - start).days <= 6 for start, end in windows)


def test_explicit_consent_revocation_blocks_chats_and_connections(pilot_api, monkeypatch):
    from app.infrastructure.database.models.product import Consent

    _, athlete, headers = scenario(pilot_api)
    thread = pilot_api.post("/api/v1/assistant/threads", headers=headers, json={"role": "athlete"}).json()

    async def revoke():
        async for db in pilot_api.app.dependency_overrides[get_db]():
            db.add(
                Consent(
                    user_id=athlete["id"],
                    scope="ai_assistant",
                    version="pilot-v1",
                    granted_at=datetime.now(UTC),
                    revoked_at=datetime.now(UTC),
                )
            )
            await db.commit()

    asyncio.run(revoke())
    result = pilot_api.post(
        f"/api/v1/assistant/threads/{thread['id']}/messages", headers=headers, json={"content": "consulta"}
    )
    assert result.status_code == 403 and "CONSENT_REQUIRED:ai_assistant" in result.text
