# ruff: noqa: F811
import asyncio
import json
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from test_privacy_notifications import enable_push, private_api  # noqa: F401

from app.api.assistant_routes import router as assistant_router
from app.api.intervals_routes import router as intervals_router
from app.core.config import settings
from app.infrastructure.database.models import User
from app.infrastructure.database.models.privacy import NotificationDelivery, NotificationPreference
from app.infrastructure.database.models.product import (
    AssistantMessage,
    AssistantThread,
    AthleteConnection,
    CoachAthleteAssignment,
    Consent,
    Job,
    Organization,
    ReviewItem,
)
from app.infrastructure.database.models.providers import AssistantRun, ProviderOAuthState
from app.services import assistant_runtime, notifications, privacy
from app.services.assistant import PROVENANCE_ONLY, REDACTED_MESSAGE
from app.services.intervals_real import SCOPES, IntervalsError, RealIntervalsAdapter, execute_intervals_disconnect_job
from app.services.vertex_assistant import VertexAssistant


@pytest.fixture
def correction_api(private_api, monkeypatch):
    api = private_api
    api.client.app.include_router(intervals_router, prefix="/api/v1")
    api.client.app.include_router(assistant_router, prefix="/api/v1")
    for field, value in {
        "INTERVALS_CLIENT_ID": "synthetic-client",
        "INTERVALS_CLIENT_SECRET": "synthetic-client-secret",
        "INTERVALS_REDIRECT_URI": "http://localhost:3000/athlete/connections/intervals/callback",
        "PROVIDER_TOKEN_ENCRYPTION_KEY": Fernet.generate_key().decode(),
        "AI_PROVIDER": "vertex",
        "AI_MODEL": "synthetic-model",
        "AI_GCP_PROJECT": "synthetic-project",
        "AI_INPUT_USD_PER_MILLION": 1.0,
        "AI_OUTPUT_USD_PER_MILLION": 1.0,
        "AI_USER_MONTHLY_BUDGET_USD": 10.0,
        "AI_ORG_MONTHLY_BUDGET_USD": 10.0,
    }.items():
        monkeypatch.setattr(settings, field, value)
    return api


def begin_oauth(api):
    athlete_id, headers = api.identities[1]
    start = api.client.post(f"/api/v1/connections/intervals/{athlete_id}/authorize", headers=headers)
    assert start.status_code == 200, start.text
    state = parse_qs(urlparse(start.json()["authorization_url"]).query)["state"][0]
    return athlete_id, headers, {"state": state, "code": "synthetic-code"}


def issued_token():
    return {"access_token": "synthetic-issued-capability", "scope": ",".join(SCOPES), "athlete": {"id": "remote-123"}}


@pytest.mark.parametrize("change", ["withdrawal", "erasure"])
def test_oauth_issued_token_cleanup_survives_simultaneous_withdrawal_or_erasure(correction_api, monkeypatch, change):
    api = correction_api
    athlete_id, headers, payload = begin_oauth(api)
    exchanged = []

    async def exchange(_self, _code):
        exchanged.append(True)
        # Callback has committed consumption and released the owner's lock before HTTP.
        async with api.sessions() as db:
            user = await db.scalar(select(User).where(User.id == athlete_id).with_for_update())
            if change == "erasure":
                await privacy.erase_account(db, user)
            else:
                db.add(
                    Consent(
                        user_id=athlete_id,
                        scope="training_data_processing",
                        version="pilot-v1",
                        granted_at=datetime.now(UTC),
                        revoked_at=datetime.now(UTC),
                    )
                )
            await db.commit()
        return issued_token()

    monkeypatch.setattr(RealIntervalsAdapter, "exchange_code", exchange)
    response = api.client.post("/api/v1/connections/intervals/callback", headers=headers, json=payload)
    assert response.status_code in (403, 404), response.text
    assert "synthetic-issued-capability" not in response.text
    retry = api.client.post("/api/v1/connections/intervals/callback", headers=headers, json=payload)
    assert retry.status_code in (400, 401, 403, 404) and len(exchanged) == 1

    async def inspect_and_retry():
        async with api.sessions() as db:
            state = await db.scalar(select(ProviderOAuthState))
            assert state is None if change == "erasure" else state.consumed_at is not None
            assert await db.scalar(select(func.count()).select_from(AthleteConnection)) == 0
            job = await db.scalar(select(Job).where(Job.kind == "intervals_disconnect"))
            assert set(job.payload) == {"token_enc"}
            encoded = job.payload["token_enc"]
            assert "synthetic-issued-capability" not in json.dumps(job.payload)
            assert (
                Fernet(settings.PROVIDER_TOKEN_ENCRYPTION_KEY.encode()).decrypt(encoded.encode())
                == b"synthetic-issued-capability"
            )
            await privacy.cancel_user_processing(db, athlete_id)
            await db.commit()
            assert await db.get(Job, job.id) is not None

            async def fail(_self, _token):
                raise IntervalsError("INTERVALS_TEMPORARILY_UNAVAILABLE", 503)

            monkeypatch.setattr(RealIntervalsAdapter, "disconnect", fail)
            with pytest.raises(IntervalsError):
                await execute_intervals_disconnect_job(db, job)
            assert job.payload == {"token_enc": encoded}

            calls = []

            async def success(_self, token):
                calls.append(token)

            monkeypatch.setattr(RealIntervalsAdapter, "disconnect", success)
            await execute_intervals_disconnect_job(db, job)
            await db.commit()
            assert calls == ["synthetic-issued-capability"] and job.payload == {"revoked": True}

    asyncio.run(inspect_and_retry())


def test_oauth_partial_scope_and_failed_http_revoke_queue_cleanup_without_retrying_state(correction_api, monkeypatch):
    api = correction_api
    _, headers, payload = begin_oauth(api)
    calls = []

    async def request(_self, method, _path, _token=None, **_kwargs):
        calls.append(method)
        if method == "POST":
            return {**issued_token(), "scope": "ACTIVITY:READ", "token_type": "Bearer"}
        raise IntervalsError("INTERVALS_TEMPORARILY_UNAVAILABLE", 503)

    monkeypatch.setattr(RealIntervalsAdapter, "request", request)
    result = api.client.post("/api/v1/connections/intervals/callback", headers=headers, json=payload)
    assert result.status_code == 422 and "REQUIRED_SCOPES_MISSING" in result.text
    assert "synthetic-issued-capability" not in result.text
    assert api.client.post("/api/v1/connections/intervals/callback", headers=headers, json=payload).status_code == 400
    assert calls == ["POST", "DELETE"]

    async def inspect():
        async with api.sessions() as db:
            job = await db.scalar(select(Job).where(Job.kind == "intervals_disconnect"))
            assert job is not None and set(job.payload) == {"token_enc"}
            assert (await db.scalar(select(ProviderOAuthState))).consumed_at is not None
            assert await db.scalar(select(func.count()).select_from(AthleteConnection)) == 0

    asyncio.run(inspect())


@pytest.mark.parametrize("rejection", ["duplicate", "integrity"])
def test_oauth_rejected_local_save_retains_cleanup_and_original_error(correction_api, monkeypatch, rejection):
    api = correction_api
    _, headers, payload = begin_oauth(api)

    async def exchange(_self, _code):
        return issued_token()

    monkeypatch.setattr(RealIntervalsAdapter, "exchange_code", exchange)
    if rejection == "duplicate":

        async def seed():
            async with api.sessions() as db:
                db.add(
                    AthleteConnection(
                        athlete_id=api.identities[2][0],
                        provider="intervals_icu",
                        external_athlete_id="remote-123",
                        status="disconnect_pending",
                    )
                )
                await db.commit()

        asyncio.run(seed())
    else:

        async def fail_save(*_args, **_kwargs):
            raise IntegrityError("synthetic race", {}, RuntimeError("synthetic unique conflict"))

        monkeypatch.setattr("app.api.intervals_routes.enqueue_sync", fail_save)
    result = api.client.post("/api/v1/connections/intervals/callback", headers=headers, json=payload)
    assert result.status_code == 409 and "ALREADY_CONNECTED" in result.text

    async def inspect():
        async with api.sessions() as db:
            assert await db.scalar(select(func.count()).select_from(Job).where(Job.kind == "intervals_disconnect")) == 1
            assert (await db.scalar(select(ProviderOAuthState))).consumed_at is not None
            assert (
                await db.scalar(
                    select(func.count())
                    .select_from(AthleteConnection)
                    .where(AthleteConnection.athlete_id == api.identities[1][0])
                )
                == 0
            )

    asyncio.run(inspect())


def prepare_general_chat(api):
    coach_id, headers = api.identities[0]
    first, _ = api.identities[1]
    second, _ = api.identities[2]

    async def seed():
        async with api.sessions() as db:
            (await db.get(User, coach_id)).is_superuser = False
            org = await db.scalar(select(Organization))
            db.add(
                CoachAthleteAssignment(organization_id=org.id, coach_id=coach_id, athlete_id=second, status="active")
            )
            for index, athlete_id in enumerate((first, second)):
                db.add(
                    ReviewItem(
                        athlete_id=athlete_id,
                        kind="complaint",
                        priority="high",
                        reason=f"Synthetic context athlete {index}",
                        dedupe_key=f"sensitive-{index}",
                        status="open",
                    )
                )
            await db.commit()

    asyncio.run(seed())
    created = api.client.post("/api/v1/assistant/threads", headers=headers, json={"role": "coach"})
    assert created.status_code == 201, created.text
    return headers, created.json()["id"], first, second


def mock_vertex(monkeypatch, handler):
    async def token():
        return "synthetic-vertex-token"

    monkeypatch.setattr(
        assistant_runtime, "VertexAssistant", lambda: VertexAssistant(httpx.MockTransport(handler), token)
    )


def stream_answer(answer, key):
    chunk = {
        "candidates": [
            {
                "content": {"parts": [{"text": json.dumps({"answer": answer, "citation_keys": [key]})}]},
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5},
    }
    return httpx.Response(200, text="data: " + json.dumps(chunk) + "\n\n")


@pytest.mark.parametrize("source", ["context", "history"])
def test_vertex_omitted_citation_revoked_during_http_never_persists_or_returns_answer(
    correction_api, monkeypatch, source
):
    api = correction_api
    headers, thread_id, first, second = prepare_general_chat(api)
    key = f"review:{first}:synthetic"
    if source == "history":

        async def seed_history():
            async with api.sessions() as db:
                db.add(
                    AssistantMessage(
                        thread_id=thread_id,
                        author="assistant",
                        content="Synthetic prior history of second athlete",
                        citations=[{"athlete_id": second, PROVENANCE_ONLY: True}],
                        created_at=datetime.now(UTC),
                    )
                )
                await db.commit()

        asyncio.run(seed_history())

        async def context(*_args):
            return {"reads": [{"athlete_id": first, "tool": "review", "data": []}]}, [{"athlete_id": first, "key": key}]

        monkeypatch.setattr(assistant_runtime, "full_context", context)

    observed = []

    async def handler(request):
        wire = request.content.decode()
        expected = "Synthetic context athlete 1" if source == "context" else "Synthetic prior history of second athlete"
        assert expected in wire
        observed.append(True)
        async with api.sessions() as db:
            await db.scalar(select(User.id).where(User.id == second).with_for_update())
            assignment = await db.scalar(
                select(CoachAthleteAssignment).where(CoachAthleteAssignment.athlete_id == second)
            )
            assignment.status = "revoked"
            await db.commit()
        # Valid source key for first athlete; prose could still derive from the second.
        if source == "context":
            body = json.loads(request.content)
            serialized = json.dumps(body)
            import re

            matches = re.findall(r"review:" + str(first) + r":[A-Za-z0-9_-]+", serialized)
            assert matches
            used_key = matches[0]
        else:
            used_key = key
        return stream_answer("Synthetic prohibited mixed athlete answer", used_key)

    mock_vertex(monkeypatch, handler)
    url = f"/api/v1/assistant/threads/{thread_id}/messages"
    result = api.client.post(
        url, headers=headers, json={"content": "Review athletes", "request_key": "race-omitted-citation"}
    )
    assert observed and result.status_code in (403, 404), result.text
    assert "Synthetic prohibited mixed athlete answer" not in result.text

    async def inspect():
        async with api.sessions() as db:
            rows = (await db.scalars(select(AssistantMessage).where(AssistantMessage.thread_id == thread_id))).all()
            assert all("Synthetic prohibited mixed athlete answer" not in row.content for row in rows)
            run = await db.scalar(select(AssistantRun))
            assert run.result is None and run.status == "failed"

    asyncio.run(inspect())


def test_complete_provenance_is_private_guards_replay_export_and_athlete_erasure(correction_api, monkeypatch):
    api = correction_api
    headers, thread_id, first, second = prepare_general_chat(api)

    async def handler(request):
        import re

        keys = re.findall(r"review:" + str(first) + r":[A-Za-z0-9_-]+", request.content.decode())
        assert keys
        return stream_answer("Synthetic answer containing second athlete evidence", keys[0])

    mock_vertex(monkeypatch, handler)
    url = f"/api/v1/assistant/threads/{thread_id}/messages"
    payload = {"content": "Review athletes", "request_key": "stored-omitted-citation"}
    first_reply = api.client.post(url, headers=headers, json=payload)
    assert first_reply.status_code == 200, first_reply.text
    assert len(first_reply.json()["citations"]) == 1
    assert PROVENANCE_ONLY not in first_reply.text and "context_athlete_ids" not in first_reply.text
    assert api.client.post(url, headers=headers, json=payload).json() == first_reply.json()

    async def revoke():
        async with api.sessions() as db:
            saved = await db.scalar(select(AssistantMessage).where(AssistantMessage.author == "assistant"))
            assert any(c.get(PROVENANCE_ONLY) and c["athlete_id"] == second for c in saved.citations)
            run = await db.scalar(select(AssistantRun))
            assert run.result["context_athlete_ids"] == [first, second]
            assignment = await db.scalar(
                select(CoachAthleteAssignment).where(CoachAthleteAssignment.athlete_id == second)
            )
            assignment.status = "revoked"
            await db.commit()

    asyncio.run(revoke())
    history = api.client.get(url, headers=headers)
    assert history.status_code == 200 and "Synthetic answer containing" not in history.text
    repeated = api.client.post(url, headers=headers, json=payload)
    assert repeated.status_code == 200 and repeated.json()["message"] == REDACTED_MESSAGE
    assert repeated.json()["citations"] == [] and "context_athlete_ids" not in repeated.text
    exported = api.client.get("/api/v1/account/export", headers=headers)
    assert exported.status_code == 200 and "Synthetic answer containing" not in exported.text
    assert "result" not in exported.json()["assistant_runs"][0]

    async def erase():
        async with api.sessions() as db:
            await privacy.erase_account(db, await db.get(User, second))
            await db.commit()
            assert await db.get(AssistantThread, thread_id) is None
            assert await db.scalar(select(func.count()).select_from(AssistantRun)) == 0
            assert (
                await db.scalar(select(func.count()).select_from(ReviewItem).where(ReviewItem.athlete_id == first)) == 1
            )

    asyncio.run(erase())


@pytest.mark.parametrize("case", ["expired", "quiet", "invalid", "valid"])
def test_notification_deadline_prevents_late_transport_and_quiet_hours_deferral(correction_api, case):
    api = correction_api
    user_id, *_ = enable_push(api)
    now = datetime(2026, 10, 1, 12, 15, tzinfo=UTC)
    sent = []

    def transport(*_args):
        sent.append(True)
        return 201

    async def inspect():
        async with api.sessions() as db:
            await notifications.queue_notification(
                db, user_id=user_id, category="plan", event_key="deadline-test", now=now
            )
            job = await db.scalar(select(Job).where(Job.kind == "send_web_push"))
            deadline = now - timedelta(seconds=1) if case == "expired" else now + timedelta(minutes=5)
            job.payload = {
                **job.payload,
                "valid_until": "not-an-ISO-date" if case == "invalid" else deadline.isoformat(),
            }
            if case == "quiet":
                preference = await db.get(NotificationPreference, user_id)
                preference.quiet_start, preference.quiet_end = "12:00", "13:00"
            await db.commit()
            await notifications.send_notification(db, job, transport=transport, now=now)
            delivery = await db.scalar(select(NotificationDelivery))
            assert delivery.status == ("delivered" if case == "valid" else "cancelled")
            assert sent == ([True] if case == "valid" else [])

    asyncio.run(inspect())
