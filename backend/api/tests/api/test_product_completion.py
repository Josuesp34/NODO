import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from test_pilot_product import invite_and_activate, register_and_login
from test_pilot_product import pilot_api as _pilot_api

from app.core.config import settings
from app.core.database import get_db
from app.domain.comparison import compare_workout, daily_load_horizon, local_day
from app.infrastructure.database.models import Activity, Base, PrescribedWorkout
from app.infrastructure.database.models.product import ActivityLap, Decision, PlanAssignment
from app.main import get_application
from app.services.physiology import extract_session_metrics


@pytest.fixture
def pilot_api(monkeypatch):
    url = os.environ.get("TEST_PRODUCT_DATABASE_URL")
    if not url:
        yield from _pilot_api.__wrapped__(monkeypatch)
        return
    # The optional PostgreSQL suite destroys only an explicitly named test database.
    if not url.rsplit("/", 1)[-1].endswith("_test"):
        raise ValueError("TEST_PRODUCT_DATABASE_URL debe terminar en _test")
    monkeypatch.setattr(settings, "ALLOW_COACH_REGISTRATION", True)
    monkeypatch.setattr(settings, "ALLOW_SUPERUSER_BOOTSTRAP", True)
    monkeypatch.setattr(settings, "DEV_SUPERUSER_BOOTSTRAP_TOKEN", "bootstrap-secret")
    monkeypatch.setattr(settings, "AI_PROVIDER", "simulated")
    engine = create_async_engine(url, poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def reset():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(reset())
    app = get_application()

    async def override():
        async with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = override
    with TestClient(app) as client:
        yield client
    asyncio.run(engine.dispose())


def payload(title="Sesión", sport="running", at="2026-09-21T01:00:00Z"):
    return {
        "title": title,
        "sport_type": sport,
        "scheduled_date": at,
        "steps": [{"repetitions": 1, "steps": [{"kind": "work", "duration_sec": 300}]}],
    }


def in_database(client, operation):
    async def run():
        async for db in client.app.dependency_overrides[get_db]():
            return await operation(db)

    return asyncio.run(run())


def setup(client):
    coach = register_and_login(client)
    athlete, own = invite_and_activate(client, coach)
    other = register_and_login(client, "other-coach@example.com")
    return coach, athlete["id"], own, other


def test_activity_pagination_detail_link_cas_and_local_comparison(pilot_api):
    coach, aid, own, other = setup(pilot_api)
    path = f"/api/v1/athletes/{aid}"
    workout = pilot_api.post(path + "/workouts", headers=coach, json=payload()).json()
    assert (
        pilot_api.post(
            path + f"/workouts/{workout['id']}/publish", headers=coach, json={"expected_version": 1}
        ).status_code
        == 200
    )

    async def seed(db):
        for index in range(3):
            activity = Activity(
                athlete_id=aid,
                file_name=f"sample-{index}.fit",
                file_hash=f"{index:064}",
                start_time=datetime(2026, 9, 21, 1, tzinfo=UTC),
                sport_type="running",
                timezone="America/Mexico_City",
                total_duration_sec=320,
                total_distance_m=1000,
            )
            db.add(activity)
            await db.flush()
            if index == 0:
                db.add(ActivityLap(activity_id=activity.id, lap_index=0, duration_sec=320, distance_m=1000))
        await db.commit()

    in_database(pilot_api, seed)
    page = pilot_api.get(path + "/activities/page?limit=2", headers=own)
    assert page.status_code == 200 and page.json()["total"] == 3 and page.json()["next_offset"] == 2
    next_page = pilot_api.get(path + "/activities/page?limit=2&offset=2", headers=coach).json()
    assert len(next_page["items"]) == 1 and next_page["next_offset"] is None
    activity = next_page["items"][0]
    assert activity["local_date"] == "2026-09-20"
    activity_path = path + f"/activities/{activity['id']}"
    assert pilot_api.get(activity_path, headers=other).status_code == 404
    assert pilot_api.get(activity_path, headers=coach).json()["laps"][0]["duration_sec"] == 320
    link = {"prescribed_workout_id": workout["id"], "expected_version": 1}
    assert pilot_api.put(activity_path + "/link", headers=own, json=link).status_code == 200
    assert pilot_api.put(activity_path + "/link", headers=own, json=link).status_code == 409
    compared = pilot_api.get(path + "/activities/comparison?start=2026-09-20&end=2026-09-20", headers=own).json()
    assert compared["workouts"][0]["status"] == "comparable"
    assert compared["workouts"][0]["summary"][0]["delta"] == 20
    assert (
        pilot_api.put(
            activity_path + "/link", headers=own, json={"prescribed_workout_id": None, "expected_version": 2}
        ).status_code
        == 200
    )
    missing = pilot_api.get(path + "/activities/comparison?start=2026-09-20&end=2026-09-20", headers=coach).json()
    assert missing["workouts"][0]["status"] == "not_synchronized"
    bike = pilot_api.post(path + "/workouts", headers=coach, json=payload(sport="cycling")).json()
    pilot_api.post(path + f"/workouts/{bike['id']}/publish", headers=coach, json={"expected_version": 1})
    assert (
        pilot_api.put(
            activity_path + "/link", headers=own, json={"prescribed_workout_id": bike["id"], "expected_version": 3}
        ).status_code
        == 422
    )
    assert pilot_api.get(path + "/workouts?start=2026-09-20&end=2026-09-20", headers=own).json()


def test_comparison_units_missing_laps_and_rest_horizon():
    workout = SimpleNamespace(
        sport_type="swimming",
        steps=[
            {
                "repetitions": 2,
                "steps": [
                    {
                        "kind": "work",
                        "distance_m": 100,
                        "target": {"metric": "pace", "unit": "sec_per_100m", "minimum": 80, "maximum": 100},
                    }
                ],
            }
        ],
    )
    activity = SimpleNamespace(sport_type="swimming", total_duration_sec=180, total_distance_m=200)
    lap = SimpleNamespace(duration_sec=90, distance_m=100, avg_heart_rate=None, avg_power=None)
    matched = compare_workout(workout, activity, [lap, lap])
    assert matched["laps"][0]["target"]["actual"] == 90
    assert matched["summary"] == [{"unit": "meters", "planned": 200, "actual": 200, "delta": 0}]
    ambiguous = compare_workout(workout, activity, [lap])
    assert ambiguous["laps"] == [] and ambiguous["quality"] == "partial"
    workout.sport_type = "running"
    assert compare_workout(workout, activity, [lap, lap])["status"] == "incompatible_discipline"
    assert local_day(datetime(2026, 9, 21, 1, tzinfo=UTC), "America/Mexico_City") == "2026-09-20"
    assert daily_load_horizon(
        date(2026, 9, 1), [date(2026, 9, 5)], datetime(2026, 9, 21, 1, tzinfo=UTC), "America/Mexico_City"
    ) == date(2026, 9, 20)


def test_template_version_updates_original_drafts_preserving_individual_edits(pilot_api):
    coach, aid, _own, other = setup(pilot_api)
    raw = {**payload(), "key": "one"}
    created = pilot_api.post(
        "/api/v1/templates", headers=coach, json={"name": "Base", "sport_type": "running", "workouts": [raw]}
    ).json()
    tpath = f"/api/v1/templates/{created['id']}"
    applied = pilot_api.post(tpath + "/apply", headers=coach, json={"athlete_ids": [aid], "expected_version": 1}).json()
    wid = applied["workout_ids"][0]
    assert pilot_api.post(tpath + "/apply", headers=coach, json={"athlete_ids": [aid]}).json()["workout_ids"] == []
    version2 = {
        "name": "Base ajustada",
        "sport_type": "running",
        "workouts": [{**raw, "title": "Nueva"}],
        "expected_version": 1,
    }
    assert pilot_api.put(tpath, headers=coach, json=version2).status_code == 200
    assert pilot_api.post(tpath + "/apply", headers=coach, json={"athlete_ids": [aid], "expected_version": 2}).json()[
        "workout_ids"
    ] == [wid]
    assert (
        pilot_api.put(
            f"/api/v1/athletes/{aid}/workouts/{wid}",
            headers=coach,
            json={**payload("Individual"), "expected_version": 2},
        ).status_code
        == 200
    )
    assert pilot_api.put(tpath, headers=coach, json={**version2, "expected_version": 2}).status_code == 200
    preserved = pilot_api.post(tpath + "/apply", headers=coach, json={"athlete_ids": [aid]}).json()
    assert preserved["workout_ids"] == [] and preserved["skipped"][0]["reason"] == "published_or_individually_edited"
    assert pilot_api.post(tpath + "/apply", headers=other, json={"athlete_ids": [aid]}).status_code == 404
    assert (
        pilot_api.post(tpath + "/apply", headers=coach, json={"athlete_ids": [aid], "expected_version": 1}).status_code
        == 409
    )

    async def verify(db):
        workouts = list(await db.scalars(select(PrescribedWorkout).where(PrescribedWorkout.athlete_id == aid)))
        assert len(workouts) == 1 and workouts[0].title == "Individual"
        assert (await db.scalar(select(PlanAssignment))).workout_refs["one"]["id"] == wid

    in_database(pilot_api, verify)


def test_recommendation_modify_once_and_reject(pilot_api):
    coach, aid, _own, other = setup(pilot_api)
    workout = pilot_api.post(f"/api/v1/athletes/{aid}/workouts", headers=coach, json=payload()).json()
    request = {"athlete_id": aid, "workout_id": workout["id"], "changes": {"title": "Propuesta"}}
    rec = pilot_api.post("/api/v1/recommendations", headers=coach, json=request).json()
    dpath = f"/api/v1/recommendations/{rec['id']}/decision"
    assert pilot_api.post(dpath, headers=other, json={"action": "approve"}).status_code == 404
    applied = pilot_api.post(
        dpath,
        headers=coach,
        json={"action": "modify", "changes": {"title": "Revisión final"}, "expected_plan_version": 1},
    ).json()
    assert applied["workout"]["title"] == "Revisión final" and applied["workout"]["version"] == 2
    assert pilot_api.post(dpath, headers=coach, json={"action": "approve"}).status_code == 409
    rec2 = pilot_api.post("/api/v1/recommendations", headers=coach, json=request).json()
    assert (
        pilot_api.post(
            f"/api/v1/recommendations/{rec2['id']}/decision", headers=coach, json={"action": "reject"}
        ).status_code
        == 200
    )

    async def verify(db):
        assert len(list(await db.scalars(select(Decision)))) == 2

    in_database(pilot_api, verify)


def test_complaint_reopen_history_and_stale_review(pilot_api):
    coach, aid, own, other = setup(pilot_api)
    complaint = pilot_api.post(
        f"/api/v1/athletes/{aid}/complaints",
        headers=own,
        json={"zone": "Rodilla", "laterality": "left", "intensity_0_10": 4, "started_on": "2026-09-20"},
    ).json()
    review = pilot_api.get("/api/v1/review-items", headers=coach).json()[0]
    dpath = f"/api/v1/review-items/{review['id']}/decision"
    assert (
        pilot_api.post(
            dpath, headers=coach, json={"status": "closed", "note": "Revisión acordada", "expected_version": 1}
        ).status_code
        == 200
    )
    cpath = f"/api/v1/complaints/{complaint['id']}"
    assert (
        pilot_api.post(
            cpath + "/updates", headers=own, json={"intensity_0_10": 3, "limits_movement": False, "expected_version": 1}
        ).status_code
        == 409
    )
    assert (
        pilot_api.post(
            cpath + "/updates", headers=own, json={"intensity_0_10": 3, "limits_movement": False, "expected_version": 2}
        ).status_code
        == 200
    )
    history = pilot_api.get(cpath, headers=own).json()
    assert history["complaint"]["status"] == "reported" and len(history["updates"]) == 1
    assert len(history["decisions"]) == 1 and history["review"]["version"] == 3
    assert pilot_api.get(cpath, headers=other).status_code == 404
    assert (
        pilot_api.post(
            dpath, headers=coach, json={"status": "closed", "note": "Copia vieja", "expected_version": 2}
        ).status_code
        == 409
    )


def test_profile_validity_competitions_and_group_member_cas(pilot_api):
    coach, aid, own, _other = setup(pilot_api)
    path = f"/api/v1/athletes/{aid}"
    profile = {"sports": ["running", "triathlon"], "timezone": "America/Mexico_City", "valid_from": "2026-01-01"}
    assert pilot_api.put(path + "/profile", headers=coach, json=profile).status_code == 200
    assert (
        pilot_api.put(path + "/profile", headers=coach, json={**profile, "valid_from": "2026-02-01"}).status_code == 200
    )
    assert pilot_api.get(path + "/profile/history", headers=own).json()[1]["valid_to"] == "2026-01-31"
    assert pilot_api.put(path + "/profile", headers=coach, json={**profile, "timezone": "Invalid"}).status_code == 422
    race = {"name": "Triatlón", "competition_date": "2026-11-01", "discipline": "triathlon"}
    competition = pilot_api.post(path + "/competitions", headers=coach, json=race).json()
    cpath = path + f"/competitions/{competition['id']}"
    assert (
        pilot_api.put(cpath, headers=coach, json={**race, "name": "Objetivo", "expected_version": 1}).status_code == 200
    )
    assert pilot_api.delete(cpath + "?expected_version=1", headers=coach).status_code == 409
    assert pilot_api.delete(cpath + "?expected_version=2", headers=coach).status_code == 204
    group = pilot_api.post("/api/v1/groups", headers=coach, json={"name": "Equipo"}).json()
    gpath = f"/api/v1/groups/{group['id']}/members"
    assert pilot_api.post(gpath, headers=coach, json={"athlete_id": aid}).status_code == 201
    assert (
        pilot_api.put(
            gpath + f"/{aid}", headers=coach, json={"overrides": {"available_weekdays": [0, 2]}, "expected_version": 1}
        ).status_code
        == 200
    )
    assert pilot_api.delete(gpath + f"/{aid}?expected_version=1", headers=coach).status_code == 409
    assert pilot_api.delete(gpath + f"/{aid}?expected_version=2", headers=coach).status_code == 204


@pytest.mark.skipif(not os.environ.get("TEST_PRODUCT_DATABASE_URL"), reason="PostgreSQL CAS concurrency suite")
def test_postgres_concurrent_proposal_decisions_apply_exactly_once(pilot_api):
    coach, aid, _own, _other = setup(pilot_api)
    workout = pilot_api.post(f"/api/v1/athletes/{aid}/workouts", headers=coach, json=payload()).json()
    recommendation = pilot_api.post(
        "/api/v1/recommendations",
        headers=coach,
        json={"athlete_id": aid, "workout_id": workout["id"], "changes": {"title": "Una sola aplicación"}},
    ).json()

    def decide(_):
        return pilot_api.post(
            f"/api/v1/recommendations/{recommendation['id']}/decision",
            headers=coach,
            json={"action": "approve", "expected_plan_version": 1},
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(decide, range(2))) == [200, 409]

    async def verify(db):
        assert len(list(await db.scalars(select(Decision)))) == 1
        assert (await db.get(PrescribedWorkout, workout["id"])).version == 2

    in_database(pilot_api, verify)


def test_fit_distance_missing_zero_and_counter_delta():
    df = pd.DataFrame({"timestamp": pd.to_datetime(["2026-09-20T10:00:00Z", "2026-09-20T10:01:00Z"])})
    assert extract_session_metrics(df)["distance_m"] is None
    assert extract_session_metrics(df, {"total_distance": 0})["distance_m"] == 0
    df["distance"] = [100, 500]
    metrics = extract_session_metrics(df)
    assert metrics["distance_m"] == 400 and metrics["distance_source"] == "record_counter_delta"
    df["distance"] = [500, 100]
    assert extract_session_metrics(df)["distance_m"] is None


def test_multirole_athlete_does_not_gain_own_draft_access(pilot_api):
    from app.infrastructure.database.models.product import UserRoleAssignment

    coach, aid, own, _other = setup(pilot_api)
    response = pilot_api.post(f"/api/v1/athletes/{aid}/workouts", headers=coach, json=payload())
    assert response.status_code == 201

    async def grant_role(db):
        db.add(UserRoleAssignment(user_id=aid, role="coach"))
        await db.commit()

    in_database(pilot_api, grant_role)
    path = f"/api/v1/athletes/{aid}/workouts?start=2026-09-20&end=2026-09-21"
    assert len(pilot_api.get(path, headers=coach).json()) == 1
    assert pilot_api.get(path, headers=own).json() == []
