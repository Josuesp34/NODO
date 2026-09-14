import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import get_db
from app.infrastructure.database.models import Base
from app.main import get_application


@pytest.fixture
def nodo_api(monkeypatch):
    monkeypatch.setattr(settings, "ALLOW_COACH_REGISTRATION", True)
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
        yield client
    asyncio.run(engine.dispose())


def coach_payload(email="coach@nodo.com"):
    return {
        "email": email,
        "password": "A-long-local-password",
        "first_name": "Ana",
        "last_name": "Coach",
        "timezone": "America/Mexico_City",
    }


def register_and_login(client, email="coach@nodo.com"):
    assert client.post("/api/v1/auth/coaches", json=coach_payload(email)).status_code == 201
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "A-long-local-password"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_athlete(client, headers, email="athlete@nodo.com"):
    response = client.post("/api/v1/auth/athletes", headers=headers, json={
        "email": email, "first_name": "Leo", "last_name": "Atleta", "timezone": "America/Mexico_City",
    })
    assert response.status_code == 201
    return response.json()


def workout_payload(block_id=None):
    return {
        "title": "Umbral", "scheduled_date": "2026-10-01T07:00:00-06:00", "sport_type": "running",
        "block_id": block_id,
        "steps": [{"repetitions": 1, "steps": [
            {"kind": "warmup", "duration_sec": 900},
            {
                "kind": "work",
                "distance_m": 1000,
                "target": {"metric": "pace", "unit": "sec_per_km", "minimum": 215, "maximum": 225},
            },
            {"kind": "cooldown", "duration_sec": 600},
        ]}],
    }


def test_coach_invites_athlete_activation_and_token_rotation(nodo_api):
    headers = register_and_login(nodo_api)
    invitation = create_athlete(nodo_api, headers)
    activation = nodo_api.post("/api/v1/auth/athletes/activate", json={
        "invitation_token": invitation["invitation_token"], "password": "A-second-long-password",
    })
    assert activation.status_code == 200
    assert nodo_api.post("/api/v1/auth/athletes/activate", json={
        "invitation_token": invitation["invitation_token"], "password": "A-second-long-password",
    }).status_code == 400
    refreshed = nodo_api.post("/api/v1/auth/refresh", json={"refresh_token": activation.json()["refresh_token"]})
    assert refreshed.status_code == 200
    reused_refresh = {"refresh_token": activation.json()["refresh_token"]}
    assert nodo_api.post("/api/v1/auth/refresh", json=reused_refresh).status_code == 401


def test_coach_can_list_only_owned_athletes(nodo_api):
    owner_headers = register_and_login(nodo_api)
    first = create_athlete(nodo_api, owner_headers, "first@nodo.com")["athlete"]
    second = create_athlete(nodo_api, owner_headers, "second@nodo.com")["athlete"]

    listed = nodo_api.get("/api/v1/auth/athletes", headers=owner_headers)
    assert listed.status_code == 200
    assert [athlete["id"] for athlete in listed.json()] == sorted([first["id"], second["id"]])
    assert all(athlete["role"] == "athlete" for athlete in listed.json())

    other_headers = register_and_login(nodo_api, "other-coach@nodo.com")
    assert nodo_api.get("/api/v1/auth/athletes", headers=other_headers).json() == []

    activation = nodo_api.post("/api/v1/auth/athletes/activate", json={
        "invitation_token": create_athlete(nodo_api, owner_headers, "third@nodo.com")["invitation_token"],
        "password": "A-third-long-password",
    })
    athlete_headers = {"Authorization": f"Bearer {activation.json()['access_token']}"}
    assert nodo_api.get("/api/v1/auth/athletes", headers=athlete_headers).status_code == 403


def test_listing_athletes_requires_authentication(nodo_api):
    assert nodo_api.get("/api/v1/auth/athletes").status_code == 401


def test_planning_owner_can_publish_and_athlete_can_read(nodo_api):
    headers = register_and_login(nodo_api)
    invitation = create_athlete(nodo_api, headers)
    athlete = invitation["athlete"]
    block = nodo_api.post(f"/api/v1/athletes/{athlete['id']}/blocks", headers=headers, json={
        "title": "Base", "start_date": "2026-09-28", "end_date": "2026-10-25",
    })
    assert block.status_code == 201
    created = nodo_api.post(
        f"/api/v1/athletes/{athlete['id']}/workouts",
        headers=headers,
        json=workout_payload(block.json()["id"]),
    )
    assert created.status_code == 201
    published = nodo_api.post(
        f"/api/v1/athletes/{athlete['id']}/workouts/{created.json()['id']}/publish",
        headers=headers,
        json={"expected_version": 1},
    )
    assert published.status_code == 200
    assert published.json()["status"] == "published"
    athlete_activation = nodo_api.post("/api/v1/auth/athletes/activate", json={
        "invitation_token": invitation["invitation_token"], "password": "A-second-long-password",
    })
    athlete_headers = {"Authorization": f"Bearer {athlete_activation.json()['access_token']}"}
    own_calendar = nodo_api.get(
        f"/api/v1/athletes/{athlete['id']}/workouts?start=2026-10-01&end=2026-10-02", headers=athlete_headers,
    )
    assert own_calendar.status_code == 200
    assert own_calendar.json()[0]["status"] == "published"
    athlete_tokens = nodo_api.post("/api/v1/auth/athletes/activate", json={
        "invitation_token": create_athlete(nodo_api, headers, "unused@nodo.com")["invitation_token"],
        "password": "A-third-long-password",
    })
    # Un atleta diferente no puede ver el calendario de otra persona.
    other_headers = {"Authorization": f"Bearer {athlete_tokens.json()['access_token']}"}
    foreign_read = nodo_api.get(
        f"/api/v1/athletes/{athlete['id']}/workouts?start=2026-10-01&end=2026-10-02",
        headers=other_headers,
    )
    assert foreign_read.status_code == 404


def test_coach_cannot_access_other_coach_athlete_or_overwrite_stale_version(nodo_api):
    owner_headers = register_and_login(nodo_api)
    athlete = create_athlete(nodo_api, owner_headers)["athlete"]
    created = nodo_api.post(f"/api/v1/athletes/{athlete['id']}/workouts", headers=owner_headers, json=workout_payload())
    assert created.status_code == 201
    replacement = workout_payload()
    replacement["expected_version"] = 1
    workout_url = f"/api/v1/athletes/{athlete['id']}/workouts/{created.json()['id']}"
    assert nodo_api.put(workout_url, headers=owner_headers, json=replacement).status_code == 200
    assert nodo_api.put(workout_url, headers=owner_headers, json=replacement).status_code == 409
    other_headers = register_and_login(nodo_api, "other-coach@nodo.com")
    assert nodo_api.get(f"/api/v1/athletes/{athlete['id']}/blocks", headers=other_headers).status_code == 404


def test_invalid_workout_contract_is_rejected_before_write(nodo_api):
    headers = register_and_login(nodo_api)
    athlete = create_athlete(nodo_api, headers)["athlete"]
    invalid = workout_payload()
    invalid["steps"][0]["steps"][1]["target"]["unit"] = "watts"
    response = nodo_api.post(f"/api/v1/athletes/{athlete['id']}/workouts", headers=headers, json=invalid)
    assert response.status_code == 422


def test_workout_must_fit_inside_selected_block(nodo_api):
    headers = register_and_login(nodo_api)
    athlete = create_athlete(nodo_api, headers)["athlete"]
    block = nodo_api.post(f"/api/v1/athletes/{athlete['id']}/blocks", headers=headers, json={
        "title": "Base", "start_date": "2026-09-28", "end_date": "2026-10-25",
    })
    assert block.status_code == 201
    invalid = workout_payload(block.json()["id"])
    invalid["scheduled_date"] = "2026-11-01T07:00:00-06:00"
    response = nodo_api.post(f"/api/v1/athletes/{athlete['id']}/workouts", headers=headers, json=invalid)
    assert response.status_code == 422


def test_development_superuser_bootstrap_requires_explicit_secret(nodo_api, monkeypatch):
    payload = coach_payload("operator@nodo.com")
    assert nodo_api.post("/api/v1/auth/superusers", json=payload).status_code == 403

    monkeypatch.setattr(settings, "ALLOW_SUPERUSER_BOOTSTRAP", True)
    monkeypatch.setattr(settings, "DEV_SUPERUSER_BOOTSTRAP_TOKEN", "local-bootstrap-key")
    created = nodo_api.post(
        "/api/v1/auth/superusers", json=payload,
        headers={"X-NODO-Development-Key": "local-bootstrap-key"},
    )
    assert created.status_code == 201
    assert created.json()["is_superuser"] is True
    assert created.json()["role"] == "coach"

    tokens = nodo_api.post("/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]})
    me = nodo_api.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens.json()['access_token']}"})
    assert me.status_code == 200
    assert me.json()["is_superuser"] is True
