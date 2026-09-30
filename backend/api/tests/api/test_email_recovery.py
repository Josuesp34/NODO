import asyncio
import json
import re
from datetime import date

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import get_db
from app.infrastructure.database.models import Base
from app.infrastructure.database.models.product import CommercialPlan, Job, Organization, Subscription
from app.main import get_application
from app.services.jobs import execute_job


@pytest.fixture
def mail_api(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "ALLOW_COACH_REGISTRATION", True)
    monkeypatch.setattr(settings, "RESEND_API_KEY", "test-only-key")
    monkeypatch.setattr(settings, "RESEND_FROM_EMAIL", "NODO <acceso@example.org>")
    monkeypatch.setattr(settings, "EMAIL_QUEUE_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "PUBLIC_APP_URL", "https://nodo.example.org")
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def setup():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(setup())
    app = get_application()

    async def override():
        async with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = override
    with TestClient(app) as client:
        yield client, sessions
    asyncio.run(engine.dispose())


def _jobs(sessions):
    async def load():
        async with sessions() as db:
            return (await db.scalars(select(Job).order_by(Job.id))).all()

    return asyncio.run(load())


def _message(job):
    return json.loads(Fernet(settings.EMAIL_QUEUE_KEY.encode()).decrypt(job.payload["ciphertext"].encode()))


def _code(message):
    match = re.search(r"\n\n([A-Za-z0-9_-]{30,})\n\n", message["text"])
    assert match is not None
    return match.group(1)


def test_production_invitation_is_queued_encrypted_and_not_exposed(mail_api, monkeypatch):
    client, sessions = mail_api
    coach = {
        "email": "coach@example.org",
        "first_name": "Ana",
        "last_name": "Coach",
        "timezone": "UTC",
        "password": "A-long-local-password",
    }
    assert client.post("/api/v1/auth/coaches", json=coach).status_code == 201
    login = client.post("/api/v1/auth/login", json={"email": coach["email"], "password": coach["password"]})

    async def subscribe():
        async with sessions() as db:
            organization = await db.scalar(select(Organization))
            plan = CommercialPlan(name="Test pilot", athlete_limit=2)
            db.add(plan)
            await db.flush()
            db.add(
                Subscription(organization_id=organization.id, plan_id=plan.id, status="active", starts_on=date.today())
            )
            await db.commit()

    asyncio.run(subscribe())
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    invitation = client.post(
        "/api/v1/auth/athletes",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
        json={"email": "athlete@example.org", "first_name": "Leo", "last_name": "Atleta", "timezone": "UTC"},
    )
    assert invitation.status_code == 201
    assert invitation.json()["invitation_token"] is None
    job = _jobs(sessions)[0]
    assert job.kind == "send_resend_email"
    assert "athlete@example.org" not in json.dumps(job.payload)
    message = _message(job)
    assert message["to"] == "athlete@example.org"
    code = _code(message)
    assert code not in json.dumps(job.payload)

    sent = []

    class StubClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, *, headers, json):
            sent.append((url, headers, json))
            return httpx.Response(200, json={"id": "test-message"})

    monkeypatch.setattr("app.services.email.httpx.AsyncClient", StubClient)

    async def deliver():
        async with sessions() as db:
            active = await db.get(Job, job.id)
            await execute_job(db, active)
            await db.refresh(active)
            return active.status, active.payload

    status, payload = asyncio.run(deliver())
    assert status == "completed"
    assert payload == {"delivered": True}
    assert sent[0][1]["Idempotency-Key"] == job.dedupe_key
    assert sent[0][2]["to"] == "athlete@example.org"


def test_password_reset_is_generic_one_time_and_revokes_sessions(mail_api):
    client, sessions = mail_api
    coach = {
        "email": "coach@example.org",
        "first_name": "Ana",
        "last_name": "Coach",
        "timezone": "UTC",
        "password": "A-long-local-password",
    }
    assert client.post("/api/v1/auth/coaches", json=coach).status_code == 201
    login = client.post("/api/v1/auth/login", json={"email": coach["email"], "password": coach["password"]})
    old_access = login.json()["access_token"]
    unknown = client.post("/api/v1/auth/password-reset/request", json={"email": "unknown@example.org"})
    known = client.post("/api/v1/auth/password-reset/request", json={"email": coach["email"]})
    assert unknown.status_code == known.status_code == 202
    assert unknown.json() == known.json()
    job = _jobs(sessions)[0]
    code = _code(_message(job))
    confirm = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"email": coach["email"], "reset_token": code, "password": "A-new-long-password"},
    )
    assert confirm.status_code == 204
    assert (
        client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"email": coach["email"], "reset_token": code, "password": "Another-long-password"},
        ).status_code
        == 400
    )
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {old_access}"}).status_code == 401
    old_login = client.post("/api/v1/auth/login", json={"email": coach["email"], "password": coach["password"]})
    new_login = client.post("/api/v1/auth/login", json={"email": coach["email"], "password": "A-new-long-password"})
    assert old_login.status_code == 401
    assert new_login.status_code == 200


def test_production_invitation_requires_email_before_creating_athlete(mail_api, monkeypatch):
    client, sessions = mail_api
    coach = {
        "email": "coach@example.org",
        "first_name": "Ana",
        "last_name": "Coach",
        "timezone": "UTC",
        "password": "A-long-local-password",
    }
    assert client.post("/api/v1/auth/coaches", json=coach).status_code == 201
    login = client.post("/api/v1/auth/login", json={"email": coach["email"], "password": coach["password"]})
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "RESEND_API_KEY", "")
    invitation = client.post(
        "/api/v1/auth/athletes",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
        json={"email": "athlete@example.org", "first_name": "Leo", "last_name": "Atleta", "timezone": "UTC"},
    )
    assert invitation.status_code == 503
    assert _jobs(sessions) == []
