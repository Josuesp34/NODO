import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from garmin_fit_sdk import Encoder, Profile
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import get_db
from app.infrastructure.database.models import Base
from app.main import get_application


@pytest.fixture
def pilot_api(monkeypatch):
    monkeypatch.setattr(settings, "ALLOW_COACH_REGISTRATION", True)
    monkeypatch.setattr(settings, "ALLOW_SUPERUSER_BOOTSTRAP", True)
    monkeypatch.setattr(settings, "DEV_SUPERUSER_BOOTSTRAP_TOKEN", "bootstrap-secret")
    monkeypatch.setattr(settings, "AI_PROVIDER", "simulated")
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
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "A-long-local-password"},
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def invite_and_activate(client, coach_headers, email="athlete@nodo.com"):
    invitation = client.post(
        "/api/v1/auth/athletes",
        headers=coach_headers,
        json={
            "email": email,
            "first_name": "Leo",
            "last_name": "Atleta",
            "timezone": "America/Mexico_City",
        },
    )
    assert invitation.status_code == 201, invitation.text
    activation = client.post(
        "/api/v1/auth/athletes/activate",
        json={
            "invitation_token": invitation.json()["invitation_token"],
            "password": "A-second-long-password",
        },
    )
    assert activation.status_code == 200
    return (
        invitation.json()["athlete"],
        {"Authorization": f"Bearer {activation.json()['access_token']}"},
    )


def make_fit():
    encoder = Encoder()
    start = datetime(2026, 9, 1, tzinfo=UTC)
    encoder.on_mesg(
        Profile["mesg_num"]["FILE_ID"],
        {"manufacturer": "development", "product": 1, "type": "activity", "time_created": start},
    )
    for second in (0, 5, 10):
        encoder.on_mesg(
            Profile["mesg_num"]["RECORD"],
            {"timestamp": start + timedelta(seconds=second), "heart_rate": 150},
        )
    encoder.on_mesg(
        Profile["mesg_num"]["LAP"],
        {
            "timestamp": start + timedelta(seconds=10),
            "start_time": start,
            "total_timer_time": 8,
            "total_distance": 40,
            "avg_heart_rate": 150,
        },
    )
    encoder.on_mesg(
        Profile["mesg_num"]["SESSION"],
        {
            "timestamp": start + timedelta(seconds=10),
            "start_time": start,
            "total_timer_time": 8,
            "total_elapsed_time": 10,
            "avg_heart_rate": 150,
            "sport": "running",
        },
    )
    return bytes(encoder.close())


def test_profile_checkin_complaint_and_review_lifecycle(pilot_api):
    coach_headers = register_and_login(pilot_api)
    athlete, athlete_headers = invite_and_activate(pilot_api, coach_headers)
    profile = pilot_api.put(
        f"/api/v1/athletes/{athlete['id']}/profile",
        headers=coach_headers,
        json={
            "sports": ["running"],
            "timezone": "America/Mexico_City",
            "rest_hr": 50,
            "max_hr": 200,
            "trimp_variant": "banister_male",
            "source": "coach",
            "valid_from": "2026-01-01",
        },
    )
    assert profile.status_code == 200, profile.text
    assert pilot_api.get(f"/api/v1/athletes/{athlete['id']}/profile", headers=athlete_headers).status_code == 200
    assert (
        pilot_api.put(
            f"/api/v1/athletes/{athlete['id']}/profile",
            headers=athlete_headers,
            json={
                "sports": ["running"],
                "timezone": "UTC",
                "valid_from": "2026-02-01",
            },
        ).status_code
        == 403
    )

    checkin = pilot_api.put(
        f"/api/v1/athletes/{athlete['id']}/checkins/2026-09-20",
        headers=athlete_headers,
        json={"local_date": "2026-09-20", "fatigue": 6, "perceived_rest": 4},
    )
    assert checkin.status_code == 200
    complaint = pilot_api.post(
        f"/api/v1/athletes/{athlete['id']}/complaints",
        headers=athlete_headers,
        json={
            "zone": "rodilla",
            "laterality": "left",
            "intensity_0_10": 4,
            "started_on": "2026-09-19",
            "limits_movement": False,
        },
    )
    assert complaint.status_code == 201
    review = pilot_api.get("/api/v1/review-items", headers=coach_headers)
    assert review.status_code == 200 and len(review.json()) == 1
    item_id = review.json()[0]["id"]
    assert (
        pilot_api.post(
            f"/api/v1/review-items/{item_id}/decision",
            headers=coach_headers,
            json={"status": "closed", "note": "Seguimiento acordado"},
        ).status_code
        == 200
    )
    worsened = pilot_api.post(
        f"/api/v1/complaints/{complaint.json()['id']}/updates",
        headers=athlete_headers,
        json={"intensity_0_10": 8, "limits_movement": True},
    )
    assert worsened.status_code == 200
    assert pilot_api.get("/api/v1/review-items", headers=coach_headers).json()[0]["priority"] == "high"


def test_authenticated_fit_is_idempotent_and_uses_profile(pilot_api):
    coach_headers = register_and_login(pilot_api)
    athlete, _ = invite_and_activate(pilot_api, coach_headers)
    pilot_api.put(
        f"/api/v1/athletes/{athlete['id']}/profile",
        headers=coach_headers,
        json={
            "sports": ["running"],
            "timezone": "America/Mexico_City",
            "rest_hr": 50,
            "max_hr": 200,
            "trimp_variant": "banister_male",
            "source": "coach",
            "valid_from": "2026-01-01",
        },
    )
    url = f"/api/v1/athletes/{athlete['id']}/activities/fit"
    first = pilot_api.post(url, headers=coach_headers, files={"file": ("run.fit", make_fit())})
    assert first.status_code == 201, first.text
    assert first.json()["trimp_status"] == "calculated"
    assert first.json()["laps_saved"] == 1
    repeated = pilot_api.post(url, headers=coach_headers, files={"file": ("run.fit", make_fit())})
    assert repeated.status_code == 200
    assert repeated.json()["activity_id"] == first.json()["activity_id"]
    assert len(pilot_api.get(f"/api/v1/athletes/{athlete['id']}/activities", headers=coach_headers).json()) == 1


def test_assistant_requires_confirmation_and_double_confirm_is_idempotent(pilot_api):
    coach_headers = register_and_login(pilot_api)
    athlete, athlete_headers = invite_and_activate(pilot_api, coach_headers)
    thread = pilot_api.post(
        "/api/v1/assistant/threads",
        headers=athlete_headers,
        json={"role": "athlete", "title": "Mis datos"},
    )
    assert thread.status_code == 201
    preview = pilot_api.post(
        f"/api/v1/assistant/threads/{thread.json()['id']}/messages",
        headers=athlete_headers,
        json={
            "content": "Quiero reportar una molestia",
            "proposed_write": {
                "operation": "create_complaint",
                "payload": {
                    "zone": "tobillo",
                    "laterality": "right",
                    "intensity_0_10": 5,
                    "started_on": "2026-09-20",
                    "limits_movement": False,
                },
            },
        },
    )
    assert preview.status_code == 200, preview.text
    confirmation = preview.json()["confirmation"]
    assert pilot_api.get(f"/api/v1/athletes/{athlete['id']}/complaints", headers=athlete_headers).json() == []
    url = f"/api/v1/assistant/confirmations/{confirmation['id']}"
    confirmed = pilot_api.post(
        url,
        headers=athlete_headers,
        json={"payload_hash": confirmation["payload_hash"]},
    )
    repeated = pilot_api.post(
        url,
        headers=athlete_headers,
        json={"payload_hash": confirmation["payload_hash"]},
    )
    assert confirmed.status_code == repeated.status_code == 200
    assert confirmed.json() == repeated.json()
    assert len(pilot_api.get(f"/api/v1/athletes/{athlete['id']}/complaints", headers=athlete_headers).json()) == 1


def test_recommendation_uses_compare_and_swap_and_only_edits_drafts(pilot_api):
    coach_headers = register_and_login(pilot_api)
    athlete, _ = invite_and_activate(pilot_api, coach_headers)
    workout_url = f"/api/v1/athletes/{athlete['id']}/workouts"
    workout_payload = {
        "title": "Base",
        "scheduled_date": "2026-10-01T07:00:00-06:00",
        "sport_type": "running",
        "steps": [{"repetitions": 1, "steps": [{"kind": "work", "duration_sec": 1800}]}],
    }
    workout = pilot_api.post(workout_url, headers=coach_headers, json=workout_payload)
    assert workout.status_code == 201, workout.text
    recommendation_payload = {
        "athlete_id": athlete["id"],
        "workout_id": workout.json()["id"],
        "evidence": [{"source": "checkin", "id": 1}],
        "changes": {"title": "Base ajustada"},
    }
    stale = pilot_api.post("/api/v1/recommendations", headers=coach_headers, json=recommendation_payload)
    assert stale.status_code == 201
    listed = pilot_api.get(
        f"/api/v1/recommendations?athlete_id={athlete['id']}&status=pending",
        headers=coach_headers,
    )
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [stale.json()["id"]]
    edited = pilot_api.put(
        f"{workout_url}/{workout.json()['id']}",
        headers=coach_headers,
        json={**workout_payload, "title": "Edición humana", "expected_version": 1},
    )
    assert edited.status_code == 200, edited.text
    stale_decision = pilot_api.post(
        f"/api/v1/recommendations/{stale.json()['id']}/decision",
        headers=coach_headers,
        json={"action": "approve"},
    )
    assert stale_decision.status_code == 409

    current = pilot_api.post("/api/v1/recommendations", headers=coach_headers, json=recommendation_payload)
    approved = pilot_api.post(
        f"/api/v1/recommendations/{current.json()['id']}/decision",
        headers=coach_headers,
        json={"action": "approve", "note": "Ajuste revisado"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"


def test_groups_templates_and_intervals_gate(pilot_api):
    coach_headers = register_and_login(pilot_api)
    athlete, athlete_headers = invite_and_activate(pilot_api, coach_headers)
    group = pilot_api.post("/api/v1/groups", headers=coach_headers, json={"name": "10K"})
    assert group.status_code == 201
    assert (
        pilot_api.post(
            f"/api/v1/groups/{group.json()['id']}/members",
            headers=coach_headers,
            json={"athlete_id": athlete["id"], "overrides": {"pace": 220}},
        ).status_code
        == 201
    )
    assert [item["id"] for item in pilot_api.get("/api/v1/groups", headers=coach_headers).json()] == [
        group.json()["id"]
    ]
    members = pilot_api.get(f"/api/v1/groups/{group.json()['id']}/members", headers=coach_headers)
    assert members.status_code == 200
    assert members.json()[0]["athlete_id"] == athlete["id"]
    workout = {
        "key": "quality",
        "title": "Series",
        "scheduled_date": "2026-10-01T07:00:00-06:00",
        "steps": [{"repetitions": 1, "steps": [{"kind": "work", "distance_m": 1000}]}],
    }
    template = pilot_api.post(
        "/api/v1/templates",
        headers=coach_headers,
        json={"name": "Semana 10K", "sport_type": "running", "workouts": [workout]},
    )
    assert template.status_code == 201, template.text
    assert [item["id"] for item in pilot_api.get("/api/v1/templates", headers=coach_headers).json()] == [
        template.json()["id"]
    ]
    apply_url = f"/api/v1/templates/{template.json()['id']}/apply"
    first = pilot_api.post(
        apply_url,
        headers=coach_headers,
        json={"athlete_ids": [athlete["id"]], "overrides": {}},
    )
    repeated = pilot_api.post(
        apply_url,
        headers=coach_headers,
        json={"athlete_ids": [athlete["id"]], "overrides": {}},
    )
    assert len(first.json()["workout_ids"]) == 1
    assert repeated.json()["workout_ids"] == []
    initial_connection = pilot_api.get(
        f"/api/v1/athletes/{athlete['id']}/connections/intervals",
        headers=athlete_headers,
    )
    assert initial_connection.status_code == 200
    assert initial_connection.json()["status"] == "not_connected"
    assert (
        pilot_api.post(
            f"/api/v1/athletes/{athlete['id']}/connections/intervals",
            headers=athlete_headers,
            json={"mode": "simulated"},
        ).status_code
        == 200
    )
    persisted_connection = pilot_api.get(
        f"/api/v1/athletes/{athlete['id']}/connections/intervals",
        headers=athlete_headers,
    )
    assert persisted_connection.status_code == 200
    assert persisted_connection.json()["status"] == "simulated"
    assert (
        pilot_api.post(
            f"/api/v1/athletes/{athlete['id']}/connections/intervals",
            headers=athlete_headers,
            json={"mode": "real"},
        ).status_code
        == 503
    )


def test_commercial_capacity_without_invented_price(pilot_api):
    coach_headers = register_and_login(pilot_api)
    organization_id = pilot_api.get("/api/v1/auth/me", headers=coach_headers).json()["organization_ids"][0]
    created_admin = pilot_api.post(
        "/api/v1/auth/superusers",
        headers={"X-NODO-Development-Key": "bootstrap-secret"},
        json=coach_payload("admin@nodo.com"),
    )
    assert created_admin.status_code == 201
    admin_login = pilot_api.post(
        "/api/v1/auth/login",
        json={"email": "admin@nodo.com", "password": "A-long-local-password"},
    )
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
    plan = pilot_api.post(
        "/api/v1/admin/commercial/plans",
        headers=admin_headers,
        json={"name": "Piloto definido por humano", "athlete_limit": 1},
    )
    assert plan.status_code == 201
    assert plan.json()["monthly_price_cents"] is None
    subscription = pilot_api.post(
        "/api/v1/admin/commercial/subscriptions",
        headers=admin_headers,
        json={
            "organization_id": organization_id,
            "plan_id": plan.json()["id"],
            "starts_on": "2026-09-20",
        },
    )
    assert subscription.status_code == 201
    invite_and_activate(pilot_api, coach_headers, "first@nodo.com")
    over_limit = pilot_api.post(
        "/api/v1/auth/athletes",
        headers=coach_headers,
        json={
            "email": "second@nodo.com",
            "first_name": "Dos",
            "last_name": "Atleta",
            "timezone": "UTC",
        },
    )
    assert over_limit.status_code == 409


def test_consent_export_and_account_deidentification(pilot_api):
    coach_headers = register_and_login(pilot_api)
    _, athlete_headers = invite_and_activate(pilot_api, coach_headers)
    consent = pilot_api.post(
        "/api/v1/consents",
        headers=athlete_headers,
        json={"scope": "training_data_processing", "version": "pilot-v1"},
    )
    assert consent.status_code == 201
    listed = pilot_api.get("/api/v1/consents", headers=athlete_headers)
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == consent.json()["id"]
    exported = pilot_api.get("/api/v1/account/export", headers=athlete_headers)
    assert exported.status_code == 200
    assert exported.json()["user"]["email"] == "athlete@nodo.com"
    assert (
        pilot_api.request(
            "DELETE",
            "/api/v1/account",
            headers=athlete_headers,
            json={"password": "wrong", "confirmation": "ELIMINAR MI CUENTA"},
        ).status_code
        == 401
    )
    deleted = pilot_api.request(
        "DELETE",
        "/api/v1/account",
        headers=athlete_headers,
        json={"password": "A-second-long-password", "confirmation": "ELIMINAR MI CUENTA"},
    )
    assert deleted.status_code == 204, deleted.text
    assert pilot_api.get("/api/v1/auth/me", headers=athlete_headers).status_code == 401
