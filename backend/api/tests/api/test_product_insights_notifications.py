import asyncio
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import func, select, update
from test_privacy_notifications import enable_push, run
from test_privacy_notifications import private_api as _private_api

from app.api.planning_routes import publish_workout
from app.api.planning_routes import router as planning_router
from app.api.product_routes import create_complaint
from app.api.product_schemas import ComplaintCreate
from app.api.schemas import PublishWorkout
from app.infrastructure.database.models import PrescribedWorkout, User
from app.infrastructure.database.models.privacy import NotificationDelivery, NotificationPreference
from app.infrastructure.database.models.product import (
    AssistantThread,
    CoachAthleteAssignment,
    Competition,
    Complaint,
    Consent,
    DailyLoad,
    Job,
    Organization,
    UserRoleAssignment,
)
from app.infrastructure.database.models.providers import AssistantBudget, AssistantRun
from app.services.notification_scheduler import schedule_workout_reminders
from app.services.notifications import send_notification
from app.services.product_notifications import dispatch_product_notification, queue_product_event


@pytest.fixture(params=["sqlite", "postgres"])
def private_api(request, monkeypatch):
    yield from _private_api.__wrapped__(request, monkeypatch)


def workout_payload(at):
    return {
        "title": "Synthetic published session",
        "scheduled_date": at.isoformat(),
        "sport_type": "running",
        "steps": [{"repetitions": 1, "steps": [{"kind": "work", "duration_sec": 600}]}],
    }


def test_publication_complaint_proposal_outbox_is_atomic_and_deduplicated(private_api):
    api = private_api
    api.client.app.include_router(planning_router, prefix="/api/v1")
    coach_id, coach = api.identities[0]
    athlete_id, own = api.identities[1]
    enable_push(api, 0)
    enable_push(api, 1)
    root = f"/api/v1/athletes/{athlete_id}"
    session = api.client.post(root + "/workouts", headers=coach, json=workout_payload(datetime.now(UTC))).json()
    publish = root + f"/workouts/{session['id']}/publish"
    assert api.client.post(publish, headers=coach, json={"expected_version": 1}).status_code == 200
    assert api.client.post(publish, headers=coach, json={"expected_version": 1}).status_code == 200
    complaint = api.client.post(
        root + "/complaints",
        headers=own,
        json={
            "zone": "synthetic",
            "laterality": "center",
            "started_on": "2026-09-30",
            "intensity_0_10": 3,
            "limits_movement": False,
            "note": "private synthetic note",
        },
    ).json()
    assert (
        api.client.post(
            f"/api/v1/complaints/{complaint['id']}/updates",
            headers=own,
            json={"intensity_0_10": 8, "limits_movement": True, "expected_version": 1, "note": "private worsening"},
        ).status_code
        == 200
    )
    draft = api.client.post(root + "/workouts", headers=coach, json=workout_payload(datetime.now(UTC))).json()
    proposal = api.client.post(
        "/api/v1/recommendations",
        headers=coach,
        json={
            "athlete_id": athlete_id,
            "workout_id": draft["id"],
            "changes": {"title": "Synthetic candidate"},
            "evidence": [],
        },
    )
    assert proposal.status_code == 201, proposal.text

    async def verify():
        async with api.sessions() as db:
            events = (await db.scalars(select(Job).where(Job.kind == "product_notification").order_by(Job.id))).all()
            assert len(events) == 4
            assert [event.payload["category"] for event in events] == ["plan", "review", "review", "review"]
            assert events[0].payload["recipient_id"] == athlete_id
            assert all(event.payload["recipient_id"] == coach_id for event in events[1:])
            assert "private synthetic" not in str([event.payload for event in events])
            # The earlier complaint version is stale: only the worsened source queues review.
            for event in events:
                assert await dispatch_product_notification(db, event)
            await db.commit()
            assert await db.scalar(select(func.count()).select_from(NotificationDelivery)) == 3
            assert await db.scalar(select(func.count()).select_from(Job).where(Job.kind == "send_web_push")) == 3
            push_jobs = (await db.scalars(select(Job).where(Job.kind == "send_web_push"))).all()
            assert all(item.payload["product_source"]["athlete_id"] == athlete_id for item in push_jobs)
            assert all("private" not in str(item.payload) for item in push_jobs)
            count_before = await db.scalar(select(func.count()).select_from(Job))
            await queue_product_event(
                db,
                recipient_id=athlete_id,
                athlete_id=athlete_id,
                category="plan",
                event_key=f"plan-published:{session['id']}:2",
                entity="workout",
                entity_id=session["id"],
                entity_version=2,
            )
            await db.commit()
            assert await db.scalar(select(func.count()).select_from(Job)) == count_before
            # A rolled-back business transaction also discards its durable event.
            await queue_product_event(
                db,
                recipient_id=athlete_id,
                athlete_id=athlete_id,
                category="plan",
                event_key="rolled-back",
                entity="workout",
                entity_id=session["id"],
                entity_version=2,
            )
            await db.rollback()
            assert await db.scalar(select(func.count()).select_from(Job)) == count_before

    run(verify())


def test_revoked_assignment_and_push_consent_do_not_queue_notifications(private_api):
    api = private_api
    coach_id, _ = api.identities[0]
    athlete_id, _ = api.identities[1]
    enable_push(api, 0)

    async def scenario():
        async with api.sessions() as db:
            complaint = Complaint(
                athlete_id=athlete_id,
                zone="synthetic",
                laterality="center",
                started_on=date(2026, 9, 30),
                intensity_0_10=2,
                status="reported",
            )
            db.add(complaint)
            await db.flush()
            await queue_product_event(
                db,
                recipient_id=coach_id,
                athlete_id=athlete_id,
                category="review",
                event_key="revoked-assignment",
                entity="complaint",
                entity_id=complaint.id,
                entity_version=1,
            )
            await db.commit()
            await db.execute(update(CoachAthleteAssignment).values(status="revoked"))
            await db.commit()
            job = await db.scalar(select(Job).where(Job.kind == "product_notification"))
            assert await dispatch_product_notification(db, job)
            await db.commit()
            assert job.payload == {"queued_devices": 0, "skipped": "source_unavailable"}
            assert await db.scalar(select(func.count()).select_from(NotificationDelivery)) == 0
            await db.execute(update(CoachAthleteAssignment).values(status="active"))
            await db.execute(
                update(Consent)
                .where(Consent.user_id == coach_id, Consent.scope == "web_push")
                .values(revoked_at=datetime.now(UTC))
            )
            await queue_product_event(
                db,
                recipient_id=coach_id,
                athlete_id=athlete_id,
                category="review",
                event_key="revoked-opt-in",
                entity="complaint",
                entity_id=complaint.id,
                entity_version=1,
            )
            await db.commit()
            newest = await db.scalar(
                select(Job).where(Job.kind == "product_notification").order_by(Job.id.desc()).limit(1)
            )
            assert await dispatch_product_notification(db, newest)
            await db.commit()
            assert newest.payload == {"queued_devices": 0}
            assert await db.scalar(select(func.count()).select_from(NotificationDelivery)) == 0

    run(scenario())


def test_reminders_use_local_day_opt_in_dedupe_and_deadline(private_api):
    api = private_api
    athlete_id, headers = api.identities[1]
    enable_push(api, 1)
    assert (
        api.client.put(
            "/api/v1/notification-preferences",
            headers=headers,
            json={"enabled": True, "categories": ["reminder"], "timezone": "America/Los_Angeles"},
        ).status_code
        == 200
    )
    now = datetime(2026, 9, 21, 0, 15, tzinfo=UTC)
    start = now + timedelta(minutes=30)

    async def scenario():
        async with api.sessions() as db:
            workout = PrescribedWorkout(
                athlete_id=athlete_id,
                coach_id=api.identities[0][0],
                title="Synthetic upcoming",
                scheduled_date=start,
                status="published",
                version=2,
                sport_type="running",
                steps=[{"repetitions": 1, "steps": [{"kind": "work", "duration_sec": 600}]}],
            )
            db.add(workout)
            await db.commit()
            assert await schedule_workout_reminders(db, now=now) == 1
            assert await schedule_workout_reminders(db, now=now) == 0
            await db.commit()
            job = await db.scalar(select(Job).where(Job.kind == "product_notification"))
            assert job.payload["event_key"].endswith(":2026-09-20")
            assert await dispatch_product_notification(db, job, now=now)
            await db.commit()
            push_job = await db.scalar(select(Job).where(Job.kind == "send_web_push"))
            assert datetime.fromisoformat(push_job.payload["valid_until"]) == start
            calls = []
            await send_notification(db, push_job, now=start, transport=lambda *_: calls.append(True))
            await db.commit()
            assert not calls
            delivery = await db.scalar(select(NotificationDelivery))
            assert delivery.status == "cancelled"
            assert await schedule_workout_reminders(db, now=start) == 0
            # Quiet hours ending after this session do not create a late reminder.
            preference = await db.get(NotificationPreference, athlete_id)
            preference.quiet_start, preference.quiet_end = "16:00", "18:00"
            workout.version = 3
            await db.commit()
            assert await schedule_workout_reminders(db, now=now) == 0
            preference.quiet_start, preference.quiet_end = None, None
            preference.categories = ["plan"]
            await db.commit()
            assert await schedule_workout_reminders(db, now=now) == 0

    run(scenario())


def test_erasure_removes_product_events_linked_to_recipient_or_athlete(private_api):
    api = private_api
    athlete_id, headers = api.identities[1]
    coach_id, _ = api.identities[0]

    async def seed():
        async with api.sessions() as db:
            for recipient_id in (athlete_id, coach_id):
                await queue_product_event(
                    db,
                    recipient_id=recipient_id,
                    athlete_id=athlete_id,
                    category="review",
                    event_key=f"erased-{recipient_id}",
                    entity="complaint",
                    entity_id=1,
                    entity_version=1,
                )
            await db.commit()

    run(seed())
    result = api.client.request(
        "DELETE",
        "/api/v1/account",
        headers=headers,
        json={"confirmation": "ELIMINAR MI CUENTA", "password": "Synthetic-test-password"},
    )
    assert result.status_code == 204, result.text

    async def verify():
        async with api.sessions() as db:
            assert await db.scalar(select(func.count()).select_from(Job).where(Job.kind == "product_notification")) == 0

    run(verify())


def test_postgres_opposite_actor_locks_do_not_deadlock_outbox_fanout(private_api):
    api = private_api
    if api.sessions.kw["bind"].dialect.name != "postgresql":
        pytest.skip("Real PostgreSQL locks are required")
    coach_id, _ = api.identities[0]
    athlete_id, _ = api.identities[1]

    async def scenario():
        async with api.sessions() as db:
            row = PrescribedWorkout(
                athlete_id=athlete_id,
                coach_id=coach_id,
                title="Synthetic concurrency",
                scheduled_date=datetime.now(UTC),
                status="draft",
                version=1,
                sport_type="running",
                steps=[{"repetitions": 1, "steps": [{"kind": "work", "duration_sec": 600}]}],
            )
            db.add(row)
            await db.commit()
            workout_id = row.id
        coach_ready, athlete_ready = asyncio.Event(), asyncio.Event()

        async def publish():
            async with api.sessions() as db:
                coach = await db.scalar(select(User).where(User.id == coach_id).with_for_update())
                coach_ready.set()
                await athlete_ready.wait()
                await publish_workout(athlete_id, workout_id, PublishWorkout(expected_version=1), coach, db)

        async def complain():
            async with api.sessions() as db:
                athlete = await db.scalar(select(User).where(User.id == athlete_id).with_for_update())
                athlete_ready.set()
                await coach_ready.wait()
                await create_complaint(
                    athlete_id,
                    ComplaintCreate(
                        zone="synthetic",
                        laterality="center",
                        started_on=date(2026, 9, 30),
                        intensity_0_10=3,
                        limits_movement=False,
                    ),
                    athlete,
                    db,
                )

        await asyncio.wait_for(asyncio.gather(publish(), complain()), timeout=10)
        async with api.sessions() as db:
            assert await db.scalar(select(func.count()).select_from(Job).where(Job.kind == "product_notification")) == 2

    run(scenario())


def test_scenarios_preserve_units_explicit_inputs_and_authority(private_api):
    api = private_api
    coach_id, coach = api.identities[0]
    athlete_id, own = api.identities[1]
    from_date = date(2026, 9, 28)

    async def seed():
        async with api.sessions() as db:
            competition = Competition(
                athlete_id=athlete_id,
                coach_id=coach_id,
                name="Synthetic event",
                competition_date=date(2026, 9, 30),
                discipline="running",
                priority="A",
            )
            db.add(competition)
            db.add(
                DailyLoad(
                    athlete_id=athlete_id,
                    local_date=from_date - timedelta(days=1),
                    load_unit="trimp",
                    load_value=0,
                    ctl=42,
                    atl=7,
                    tsb=35,
                    formula_version="ewma-42-7-v1",
                    recomputed_at=datetime.now(UTC),
                )
            )
            db.add(
                Complaint(
                    athlete_id=athlete_id,
                    zone="synthetic",
                    laterality="center",
                    started_on=date(2026, 9, 30),
                    intensity_0_10=2,
                    status="reported",
                )
            )
            await db.commit()
            return competition.id

    competition_id = run(seed())
    path = f"/api/v1/athletes/{athlete_id}/competitions/{competition_id}/scenarios"
    payload = {
        "expected_competition_version": 1,
        "start_date": str(from_date),
        "load_unit": "trimp",
        "alternatives": [{"name": "A", "daily_loads": [0, 0, 0]}, {"name": "B", "daily_loads": [84, 0, 0]}],
    }
    response = api.client.post(path, headers=coach, json=payload)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "projected" and result["load_unit"] == "trimp"
    assert result["initial_state"]["local_date"] == "2026-09-27"
    assert result["review_note"] and result["unresolved_complaints"] == 1
    for alternative in result["alternatives"]:
        assert alternative["assumptions"] and alternative["formula_version"] == "ewma-42-7-v1"
        assert alternative["initial_state"]["load_unit"] == "trimp"
        assert len(alternative["days"]) == 3
    assert result["alternatives"][0]["days"][0] == {
        "local_date": "2026-09-28",
        "load": 0,
        "ctl": 41,
        "atl": 6,
        "tsb": 35,
    }
    assert result["alternatives"][1]["days"][0]["ctl"] == 43
    assert result["alternatives"][1]["days"][0]["atl"] == 18
    assert api.client.post(path, headers=own, json=payload).status_code == 403
    assert api.client.post(path, headers=coach, json={**payload, "expected_competition_version": 2}).status_code == 409
    missing = api.client.post(path, headers=coach, json={**payload, "load_unit": "tss"}).json()
    assert missing["status"] == "insufficient_initial_state"
    assert missing["alternatives"][0]["days"][0]["ctl"] is None
    assumed = api.client.post(
        path,
        headers=coach,
        json={
            **payload,
            "load_unit": "tss",
            "initial_state": {"ctl": 10, "atl": 20, "explanation": "Explicit synthetic state"},
        },
    ).json()
    assert assumed["initial_state"]["source"] == "explicit_coach_assumption"
    for invalid in (
        {**payload, "load_unit": "trimp+tss"},
        {**payload, "alternatives": [{"name": "A", "daily_loads": [0]}, {"name": "B", "daily_loads": [0]}]},
        {
            **payload,
            "alternatives": [{"name": "A", "daily_loads": [-1, 0, 0]}, {"name": "B", "daily_loads": [0, 0, 0]}],
        },
    ):
        assert api.client.post(path, headers=coach, json=invalid).status_code == 422


def test_ai_costs_sum_runs_once_separate_unknown_reservations_and_deny_cross_user(private_api):
    api = private_api
    coach_id, admin = api.identities[0]
    athlete_id, own = api.identities[1]
    month = datetime.now(UTC).date().replace(day=1)

    async def seed():
        async with api.sessions() as db:
            db.add(UserRoleAssignment(user_id=coach_id, role="athlete"))
            for user_id in (coach_id, athlete_id):
                thread = AssistantThread(
                    owner_id=user_id, role="coach" if user_id == coach_id else "athlete", title="Sensitive private chat"
                )
                db.add(thread)
                await db.flush()
                for key, status, cost in (
                    ("done", "completed", 100),
                    ("active", "running", 200),
                    ("failed", "failed", 300),
                    ("cancelled", "cancelled", 400),
                ):
                    db.add(
                        AssistantRun(
                            user_id=user_id,
                            thread_id=thread.id,
                            request_key=key,
                            request_hash="a" * 64,
                            status=status,
                            input_tokens=10,
                            output_tokens=20,
                            cost_microusd=cost,
                            result={"secret": "private prompt"},
                        )
                    )
                db.add(
                    AssistantBudget(
                        scope="user", scope_id=user_id, month=month, requests=4, tokens=120, cost_microusd=1000
                    )
                )
            org = await db.scalar(select(Organization))
            db.add(
                AssistantBudget(
                    scope="organization", scope_id=org.id, month=month, requests=8, tokens=240, cost_microusd=2000
                )
            )
            await db.commit()

    run(seed())
    response = api.client.get(f"/api/v1/admin/commercial/ai-costs?month={month}", headers=admin)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["totals"]["estimated_completed_microusd"] == 200
    assert result["totals"]["in_flight_reserved_microusd"] == 400
    assert result["totals"]["uncertain_reserved_microusd"] == 1400
    assert len(result["users"]) == 2
    assert result["users"][0]["roles"] == ["athlete", "coach"]
    org = next(row for row in result["budgets"] if row["scope"] == "organization")
    assert org["active_athletes"] == 1 and org["active_coaches"] == 1
    assert org["budget_usage_per_active_athlete_microusd"] == 2000
    assert "private prompt" not in response.text and "Sensitive private chat" not in response.text
    assert api.client.get("/api/v1/admin/commercial/ai-costs", headers=own).status_code == 403
    personal = api.client.get(f"/api/v1/account/ai-costs?month={month}", headers=own).json()
    assert len(personal["users"]) == 1 and personal["users"][0]["user_id"] == athlete_id
    assert personal["totals"]["estimated_completed_microusd"] == 100
    assert all(row["scope"] == "user" and row["scope_id"] == athlete_id for row in personal["budgets"])
    assert api.client.get("/api/v1/account/ai-costs?month=2026-09-15", headers=own).status_code == 422


def test_sync_problem_fanout_revalidates_connection_and_specific_organization(private_api):
    from app.infrastructure.database.models.product import AthleteConnection
    from app.services.product_notifications import notify_sync_problem

    api = private_api
    athlete_id, _ = api.identities[1]
    for index in (0, 1):
        enable_push(api, index)
        assert (
            api.client.put(
                "/api/v1/notification-preferences",
                headers=api.identities[index][1],
                json={"enabled": True, "categories": ["sync"], "timezone": "UTC"},
            ).status_code
            == 200
        )

    async def scenario():
        async with api.sessions() as db:
            connection = AthleteConnection(athlete_id=athlete_id, provider="intervals_icu", status="reconnect_required")
            db.add(connection)
            await db.flush()
            await notify_sync_problem(
                db, athlete_id=athlete_id, connection_id=connection.id, episode_key="test-episode"
            )
            await notify_sync_problem(
                db, athlete_id=athlete_id, connection_id=connection.id, episode_key="test-episode"
            )
            await db.commit()
            events = (await db.scalars(select(Job).where(Job.kind == "product_notification"))).all()
            assert len(events) == 2
            connection.status = "connected"
            await db.commit()
            for event in events:
                await dispatch_product_notification(db, event)
            await db.commit()
            assert await db.scalar(select(func.count()).select_from(NotificationDelivery)) == 0
            connection.status = "reconnect_required"
            await notify_sync_problem(
                db, athlete_id=athlete_id, connection_id=connection.id, episode_key="second-episode"
            )
            await db.commit()
            # A suspended assignment organization blocks coach notifications even
            # for a user whose unrelated memberships/capabilities remain active.
            organization = await db.scalar(select(Organization))
            organization.status = "suspended"
            await db.commit()
            events = (
                await db.scalars(select(Job).where(Job.kind == "product_notification").order_by(Job.id.desc()).limit(2))
            ).all()
            for event in events:
                await dispatch_product_notification(db, event)
            await db.commit()
            deliveries = (await db.scalars(select(NotificationDelivery))).all()
            assert len(deliveries) == 1 and deliveries[0].user_id == athlete_id

    run(scenario())


def test_concurrent_postgres_schedulers_keep_one_reminder(private_api):
    api = private_api
    if api.sessions.kw["bind"].dialect.name != "postgresql":
        pytest.skip("Real PostgreSQL conflicts are required")
    athlete_id, headers = api.identities[1]
    enable_push(api, 1)
    assert (
        api.client.put(
            "/api/v1/notification-preferences",
            headers=headers,
            json={"enabled": True, "categories": ["reminder"], "timezone": "UTC"},
        ).status_code
        == 200
    )
    now = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)

    async def scenario():
        async with api.sessions() as db:
            db.add(
                PrescribedWorkout(
                    athlete_id=athlete_id,
                    coach_id=api.identities[0][0],
                    title="Synthetic concurrent reminder",
                    scheduled_date=now + timedelta(minutes=30),
                    status="published",
                    version=2,
                    sport_type="running",
                    steps=[{"repetitions": 1, "steps": [{"kind": "work", "duration_sec": 600}]}],
                )
            )
            await db.commit()

        async def schedule():
            async with api.sessions() as db:
                count = await schedule_workout_reminders(db, now=now)
                await db.commit()
                return count

        assert sorted(await asyncio.wait_for(asyncio.gather(schedule(), schedule()), timeout=10)) == [0, 1]
        async with api.sessions() as db:
            assert await db.scalar(select(func.count()).select_from(Job).where(Job.kind == "product_notification")) == 1

    run(scenario())
