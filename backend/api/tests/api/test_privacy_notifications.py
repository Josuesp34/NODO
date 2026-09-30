import asyncio
import base64
import json
import os
import uuid
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool, StaticPool

from app.api.auth_routes import router as auth_router
from app.api.privacy_routes import router as privacy_router
from app.api.product_routes import router as product_router
from app.core.config import settings
from app.core.database import get_db
from app.core.security import hash_password, new_tokens
from app.infrastructure.database.models import Activity, AuthSession, Base, PrescribedWorkout, TrainingBlock, User
from app.infrastructure.database.models.privacy import (
    NotificationDelivery,
    NotificationPreference,
    PrivacyArtifact,
    PushSubscription,
)
from app.infrastructure.database.models.product import (
    ActivityLap,
    AssistantConfirmation,
    AssistantMessage,
    AssistantThread,
    AthleteConnection,
    Checkin,
    CoachAthleteAssignment,
    CommercialPlan,
    Complaint,
    ComplaintUpdate,
    Decision,
    Job,
    ManagedPayment,
    Organization,
    OrganizationMembership,
    Recommendation,
    ReviewItem,
    Subscription,
    UserRoleAssignment,
)
from app.services import access, notifications, privacy, privacy_jobs


def run(coro):
    return asyncio.run(coro)


def encoded(value):
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def push_info(endpoint="https://fcm.googleapis.com/fcm/send/synthetic-device"):
    public = (
        ec.generate_private_key(ec.SECP256R1())
        .public_key()
        .public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    )
    return {"endpoint": endpoint, "keys": {"auth": encoded(os.urandom(16)), "p256dh": encoded(public)}}


@pytest.fixture(params=["sqlite", "postgres"])
def private_api(request, monkeypatch):
    database_url = os.environ.get("NODO_PRIVACY_TEST_DATABASE_URL")
    if request.param == "postgres" and not database_url:
        pytest.skip("NODO_PRIVACY_TEST_DATABASE_URL is required for the isolated PostgreSQL cycle")
    config = SimpleNamespace(**settings.model_dump())
    config.PUSH_ENCRYPTION_KEY = Fernet.generate_key().decode()
    key = ec.generate_private_key(ec.SECP256R1())
    config.WEB_PUSH_PUBLIC_KEY = encoded(
        key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    )
    config.WEB_PUSH_PRIVATE_KEY = encoded(key.private_numbers().private_value.to_bytes(32, "big"))
    config.WEB_PUSH_CONTACT = "mailto:synthetic@example.com"
    config.PUSH_ENDPOINT_HOSTS = notifications.DEFAULT_PUSH_HOSTS
    config.WEB_PUSH_TTL_SECONDS = 3600
    config.ENVIRONMENT = "development"
    config.RETENTION_OUTBOX_DAYS = 7
    config.RETENTION_JOB_INTERVAL_HOURS = 24
    config.PRIVACY_STORAGE_ROOT = ""
    config.PRIVACY_GCS_BUCKETS = ""
    for module in (notifications, privacy, privacy_jobs, access):
        monkeypatch.setattr(module, "settings", config)
    if request.param == "postgres":
        schema = f"privacy_test_{uuid.uuid4().hex}"
        admin_engine = create_async_engine(database_url, poolclass=NullPool)

        async def create_schema():
            async with admin_engine.begin() as db:
                await db.execute(text(f'CREATE SCHEMA "{schema}"'))

        run(create_schema())
        engine = create_async_engine(
            database_url, poolclass=NullPool, connect_args={"server_settings": {"search_path": schema}}
        )
    else:
        engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)

        @event.listens_for(engine.sync_engine, "connect")
        def enforce_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def seed():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        identities = []
        async with sessions() as db:
            for index in range(3):
                user = User(
                    email=f"synthetic-{index}@example.com",
                    first_name="Synthetic",
                    last_name=str(index),
                    timezone="UTC",
                    role="coach" if index == 0 else "athlete",
                    hashed_password=hash_password("Synthetic-test-password"),
                    is_superuser=index == 0,
                )
                db.add(user)
                await db.flush()
                db.add(UserRoleAssignment(user_id=user.id, role="coach" if index == 0 else "athlete"))
                stored, tokens = new_tokens()
                db.add(AuthSession(user_id=user.id, **stored))
                identities.append((user.id, {"Authorization": f"Bearer {tokens['access_token']}"}))
            org = Organization(name="Synthetic org", slug="synthetic-org")
            db.add(org)
            await db.flush()
            db.add(
                OrganizationMembership(organization_id=org.id, user_id=identities[0][0], role="owner", status="active")
            )
            db.add(
                CoachAthleteAssignment(
                    organization_id=org.id, coach_id=identities[0][0], athlete_id=identities[1][0], status="active"
                )
            )
            await db.commit()
        return identities

    identities = run(seed())
    app = FastAPI()
    app.include_router(privacy_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(product_router, prefix="/api/v1")

    async def override():
        async with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override
    with TestClient(app) as client:
        yield SimpleNamespace(client=client, sessions=sessions, identities=identities, config=config)
    run(engine.dispose())
    if request.param == "postgres":

        async def cleanup():
            async with admin_engine.begin() as db:
                await db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            await admin_engine.dispose()

        run(cleanup())


def enable_push(api, identity_index=1):
    user_id, headers = api.identities[identity_index]
    consent = api.client.post("/api/v1/consents", headers=headers, json={"scope": "web_push", "version": "pilot-v1"})
    assert consent.status_code == 201, consent.text
    assert (
        api.client.put(
            "/api/v1/notification-preferences",
            headers=headers,
            json={"enabled": True, "categories": ["plan", "review"], "timezone": "UTC"},
        ).status_code
        == 200
    )
    info = push_info(f"https://fcm.googleapis.com/fcm/send/synthetic-{user_id}")
    subscription = api.client.post("/api/v1/push-subscriptions", headers=headers, json=info)
    assert subscription.status_code == 201, subscription.text
    return user_id, headers, info, subscription.json(), consent.json()


def test_push_encrypts_deduplicates_and_delivers_only_minimal_payload(private_api):
    api = private_api
    user_id, _, info, _, _ = enable_push(api)

    async def scenario():
        async with api.sessions() as db:
            assert (
                await notifications.queue_notification(db, user_id=user_id, category="plan", event_key="published:1:2")
                == 1
            )
            assert (
                await notifications.queue_notification(db, user_id=user_id, category="plan", event_key="published:1:2")
                == 0
            )
            await db.commit()
            sub = await db.scalar(select(PushSubscription).where(PushSubscription.user_id == user_id))
            assert info["endpoint"] not in sub.subscription_enc and info["keys"]["auth"] not in sub.subscription_enc
            job = await db.scalar(select(Job).where(Job.kind == "send_web_push"))
            assert list(job.payload) == ["delivery_id"]
            delivered = []

            def transport(subscription_info, payload):
                delivered.append(json.loads(payload))
                assert subscription_info == info
                return 201

            await notifications.send_notification(db, job, transport=transport)
            await db.commit()
            await notifications.send_notification(db, job, transport=transport)
            assert len(delivered) == 1
            assert set(delivered[0]) == {"title", "body", "url", "tag"}
            assert "Synthetic" not in json.dumps(delivered[0])
            assert (await db.get(NotificationDelivery, job.payload["delivery_id"])).status == "delivered"

    run(scenario())


def test_revocation_cancels_queued_push_and_cross_account_revoke_is_denied(private_api):
    api = private_api
    user_id, headers, _, subscription, consent = enable_push(api)

    async def enqueue():
        async with api.sessions() as db:
            await notifications.queue_notification(db, user_id=user_id, category="review", event_key="review:1")
            await db.commit()

    run(enqueue())
    other_headers = api.identities[2][1]
    assert (
        api.client.delete(f"/api/v1/push-subscriptions/{subscription['id']}", headers=other_headers).status_code == 404
    )
    assert api.client.delete(f"/api/v1/consents/{consent['id']}", headers=headers).status_code == 204

    async def scenario():
        async with api.sessions() as db:
            job = await db.scalar(select(Job).where(Job.kind == "send_web_push"))
            await notifications.send_notification(
                db, job, transport=lambda *_: pytest.fail("Revoked delivery reached transport")
            )
            sub = await db.get(PushSubscription, subscription["id"])
            assert sub.subscription_enc is None and sub.revoked_at
            assert (
                await notifications.queue_notification(db, user_id=user_id, category="review", event_key="review:2")
                == 0
            )

    run(scenario())


def test_expired_endpoint_is_removed_and_quiet_hours_reschedule(private_api):
    api = private_api
    user_id, _, _, subscription, _ = enable_push(api)

    async def scenario():
        async with api.sessions() as db:
            preference = await db.get(NotificationPreference, user_id)
            preference.quiet_start, preference.quiet_end, preference.timezone = "22:00", "07:00", "America/Mexico_City"
            now = datetime(2026, 10, 1, 5, tzinfo=UTC)
            await notifications.queue_notification(db, user_id=user_id, category="plan", event_key="quiet", now=now)
            job = await db.scalar(select(Job).where(Job.kind == "send_web_push"))
            assert notifications.aware(job.run_after) == datetime(2026, 10, 1, 13, tzinfo=UTC)
            with pytest.raises(notifications.PushDeferred):
                await notifications.send_notification(
                    db, job, now=now, transport=lambda *_: pytest.fail("Quiet delivery reached transport")
                )
            await notifications.send_notification(
                db, job, now=datetime(2026, 10, 1, 14, tzinfo=UTC), transport=lambda *_: 410
            )
            assert (await db.get(PushSubscription, subscription["id"])).subscription_enc is None
            assert (await db.get(NotificationDelivery, job.payload["delivery_id"])).status == "expired"

    run(scenario())


def test_endpoint_validation_denies_private_destinations_and_endpoint_transfer(private_api):
    api = private_api
    _, _, info, _, _ = enable_push(api)
    _, other_headers, _, _, _ = enable_push(api, 2)
    for endpoint in (
        "https://127.0.0.1/push",
        "https://fcm.googleapis.com.evil.example/push",
        "https://fcm.googleapis.com:8443/push",
        "https://user:pass@fcm.googleapis.com/push",
        "http://fcm.googleapis.com/push",
    ):
        rejected = api.client.post(
            "/api/v1/push-subscriptions", headers=other_headers, json={**info, "endpoint": endpoint}
        )
        assert rejected.status_code == 422
    assert api.client.post("/api/v1/push-subscriptions", headers=other_headers, json=info).status_code == 409


def test_training_withdrawal_blocks_use_and_clears_tokens_jobs_but_allows_export(private_api):
    api = private_api
    user_id, headers = api.identities[1]
    consent = api.client.post(
        "/api/v1/consents", headers=headers, json={"scope": "training_data_processing", "version": "pilot-v1"}
    ).json()

    async def seed():
        async with api.sessions() as db:
            db.add(
                AthleteConnection(
                    athlete_id=user_id,
                    provider="intervals_icu",
                    status="connected",
                    access_token_enc="synthetic-token",
                    refresh_token_enc="synthetic-refresh",
                    scopes=["ACTIVITY"],
                )
            )
            db.add(Job(kind="intervals_sync", payload={"athlete_id": user_id}, run_after=datetime.now(UTC)))
            db.add(
                Job(kind="intervals_sync", payload={"athlete_id": api.identities[2][0]}, run_after=datetime.now(UTC))
            )
            await db.commit()

    run(seed())
    assert api.client.delete(f"/api/v1/consents/{consent['id']}", headers=headers).status_code == 204
    assert api.client.get(f"/api/v1/athletes/{user_id}/profile", headers=headers).status_code == 403
    exported = api.client.get("/api/v1/account/export", headers=headers)
    assert exported.status_code == 200 and "synthetic-token" not in exported.text

    async def verify():
        async with api.sessions() as db:
            connection = await db.scalar(select(AthleteConnection).where(AthleteConnection.athlete_id == user_id))
            assert (
                connection.status == "revoked"
                and connection.access_token_enc is None
                and connection.refresh_token_enc is None
            )
            jobs = (await db.scalars(select(Job).where(Job.kind == "intervals_sync"))).all()
            assert len(jobs) == 1 and jobs[0].payload["athlete_id"] == api.identities[2][0]

    run(verify())


def test_account_erasure_follows_fks_and_removes_derived_chats_preserving_other_athlete(private_api):
    api = private_api
    coach_id, _ = api.identities[0]
    athlete_id, headers = api.identities[1]
    other_id, _ = api.identities[2]
    now = datetime.now(UTC)

    async def seed():
        async with api.sessions() as db:
            block = TrainingBlock(
                athlete_id=athlete_id,
                coach_id=coach_id,
                title="Private block",
                start_date=date.today(),
                end_date=date.today(),
            )
            db.add(block)
            await db.flush()
            workout = PrescribedWorkout(
                athlete_id=athlete_id, coach_id=coach_id, title="Private plan", scheduled_date=now, block_id=block.id
            )
            db.add(workout)
            await db.flush()
            activity = Activity(
                athlete_id=athlete_id,
                file_name="synthetic.fit",
                file_hash="a" * 64,
                start_time=now,
                prescribed_workout_id=workout.id,
            )
            db.add(activity)
            await db.flush()
            db.add(ActivityLap(activity_id=activity.id, lap_index=1))
            recommendation = Recommendation(
                coach_id=coach_id,
                athlete_id=athlete_id,
                workout_id=workout.id,
                base_plan_version=1,
                changes={"title": "Private"},
                rules_version="test",
                model_version="test",
            )
            db.add(recommendation)
            await db.flush()
            db.add(Decision(recommendation_id=recommendation.id, actor_id=coach_id, action="reject", decided_at=now))
            complaint = Complaint(
                athlete_id=athlete_id, zone="synthetic", laterality="left", intensity_0_10=4, started_on=date.today()
            )
            db.add(complaint)
            await db.flush()
            db.add(
                ComplaintUpdate(complaint_id=complaint.id, actor_id=coach_id, intensity_0_10=3, limits_movement=False)
            )
            db.add(
                ReviewItem(
                    athlete_id=athlete_id,
                    complaint_id=complaint.id,
                    kind="complaint",
                    priority="review",
                    reason="synthetic",
                    dedupe_key="synthetic-complaint-review",
                )
            )
            thread = AssistantThread(owner_id=coach_id, role="coach", title="Private derived chat")
            db.add(thread)
            await db.flush()
            db.add(
                AssistantMessage(
                    thread_id=thread.id,
                    author="assistant",
                    content="Private prose about first athlete",
                    created_at=now,
                    citations=[{"athlete_id": athlete_id}],
                )
            )
            db.add(
                AssistantConfirmation(
                    thread_id=thread.id,
                    user_id=coach_id,
                    operation="test",
                    payload={"athlete_id": athlete_id},
                    payload_hash="b" * 64,
                    expires_at=now + timedelta(hours=1),
                )
            )
            db.add(Checkin(athlete_id=other_id, local_date=date.today(), notes="Other athlete survives"))
            await db.commit()

    run(seed())
    exported = api.client.get("/api/v1/account/export", headers=headers)
    assert exported.status_code == 200
    assert "Private block" in exported.text and "Other athlete survives" not in exported.text
    assert "Private prose" not in exported.text and "hashed_password" not in exported.text
    deleted = api.client.request(
        "DELETE",
        "/api/v1/account",
        headers=headers,
        json={"password": "Synthetic-test-password", "confirmation": "ELIMINAR MI CUENTA"},
    )
    assert deleted.status_code == 204, deleted.text
    assert api.client.get("/api/v1/auth/me", headers=headers).status_code == 401

    async def verify():
        async with api.sessions() as db:
            for model in (
                Activity,
                ActivityLap,
                PrescribedWorkout,
                TrainingBlock,
                Recommendation,
                Decision,
                Complaint,
                ComplaintUpdate,
                ReviewItem,
                AssistantThread,
                AssistantMessage,
                AssistantConfirmation,
            ):
                assert await db.scalar(select(func.count()).select_from(model)) == 0
            assert (
                await db.scalar(select(Checkin.notes).where(Checkin.athlete_id == other_id)) == "Other athlete survives"
            )
            user = await db.get(User, athlete_id)
            assert user.deleted_at and user.email.endswith("@invalid.local") and not user.is_superuser
            job = await db.scalar(select(Job).where(Job.kind == "privacy_delete_user_files"))
            assert job.payload == {"user_id": athlete_id}

    run(verify())


def test_coach_erasure_preserves_payment_fk_and_unlinks_other_athlete_activity(private_api):
    api = private_api
    coach_id, headers = api.identities[0]
    athlete_id, _ = api.identities[1]

    async def seed():
        async with api.sessions() as db:
            org = await db.scalar(select(Organization))
            plan = CommercialPlan(name="Synthetic agreement", athlete_limit=2)
            db.add(plan)
            await db.flush()
            subscription = Subscription(
                organization_id=org.id, plan_id=plan.id, status="active", starts_on=date.today()
            )
            db.add(subscription)
            await db.flush()
            db.add(
                ManagedPayment(
                    subscription_id=subscription.id,
                    amount_cents=100,
                    currency="MXN",
                    paid_on=date.today(),
                    reference="synthetic-ref",
                    recorded_by=coach_id,
                )
            )
            block = TrainingBlock(
                athlete_id=athlete_id,
                coach_id=coach_id,
                title="Coach-owned",
                start_date=date.today(),
                end_date=date.today(),
            )
            db.add(block)
            await db.flush()
            workout = PrescribedWorkout(
                athlete_id=athlete_id,
                coach_id=coach_id,
                block_id=block.id,
                title="Coach-owned",
                scheduled_date=datetime.now(UTC),
            )
            db.add(workout)
            await db.flush()
            db.add(
                Activity(
                    athlete_id=athlete_id,
                    file_name="synthetic.fit",
                    file_hash="c" * 64,
                    start_time=datetime.now(UTC),
                    prescribed_workout_id=workout.id,
                )
            )
            athlete = await db.get(User, athlete_id)
            athlete.coach_id = coach_id
            await db.commit()

    run(seed())
    deleted = api.client.request(
        "DELETE",
        "/api/v1/account",
        headers=headers,
        json={"password": "Synthetic-test-password", "confirmation": "ELIMINAR MI CUENTA"},
    )
    assert deleted.status_code == 204, deleted.text

    async def verify():
        async with api.sessions() as db:
            payment = await db.scalar(select(ManagedPayment))
            assert payment.recorded_by == coach_id
            assert (await db.get(User, coach_id)).deleted_at
            assert (await db.get(User, athlete_id)).coach_id is None
            activity = await db.scalar(select(Activity))
            assert activity.athlete_id == athlete_id and activity.prescribed_workout_id is None
            assert await db.scalar(select(func.count()).select_from(PrescribedWorkout)) == 0
            assert (await db.scalar(select(Organization))).status == "suspended"

    run(verify())


def test_retention_deletes_old_sources_and_outbox_and_keeps_recent_records(private_api):
    api = private_api
    user_id, _ = api.identities[1]
    now = datetime.now(UTC)

    async def scenario():
        async with api.sessions() as db:
            old = Activity(
                athlete_id=user_id, file_name="old.fit", file_hash="d" * 64, start_time=now - timedelta(days=366)
            )
            db.add(old)
            await db.flush()
            db.add(ActivityLap(activity_id=old.id, lap_index=1))
            db.add(Activity(athlete_id=user_id, file_name="recent.fit", file_hash="e" * 64, start_time=now))
            block = TrainingBlock(
                athlete_id=user_id,
                coach_id=api.identities[0][0],
                title="Expired block",
                start_date=(now - timedelta(days=400)).date(),
                end_date=(now - timedelta(days=366)).date(),
            )
            db.add(block)
            await db.flush()
            workout = PrescribedWorkout(
                athlete_id=user_id,
                coach_id=api.identities[0][0],
                title="Expired workout",
                scheduled_date=now - timedelta(days=366),
                block_id=block.id,
            )
            db.add(workout)
            await db.flush()
            recommendation = Recommendation(
                athlete_id=user_id,
                coach_id=api.identities[0][0],
                workout_id=workout.id,
                base_plan_version=1,
                changes={},
                rules_version="test",
                model_version="test",
            )
            db.add(recommendation)
            await db.flush()
            db.add(
                Decision(
                    recommendation_id=recommendation.id,
                    actor_id=api.identities[0][0],
                    action="reject",
                    decided_at=now,
                    note="Expired source decision",
                )
            )
            db.add(
                Job(
                    kind="send_resend_email",
                    payload={"ciphertext": "synthetic"},
                    run_after=now,
                    created_at=now - timedelta(days=8),
                    updated_at=now - timedelta(days=8),
                )
            )
            db.add(
                Job(
                    kind="privacy_delete_user_files",
                    payload={"user_id": user_id},
                    run_after=now,
                    created_at=now - timedelta(days=8),
                    updated_at=now - timedelta(days=8),
                )
            )
            db.add(
                Job(
                    kind="intervals_disconnect",
                    payload={"token_enc": "synthetic-ciphertext"},
                    run_after=now,
                    created_at=now - timedelta(days=8),
                    updated_at=now - timedelta(days=8),
                )
            )
            await db.commit()
            counts = await privacy.sweep_retention(db, now=now)
            await db.commit()
            assert counts["activities"] == 1 and counts["jobs"] == 1
            assert await db.scalar(select(func.count()).select_from(ActivityLap)) == 0
            assert (await db.scalar(select(Activity))).file_name == "recent.fit"
            assert set((await db.scalars(select(Job.kind))).all()) == {
                "privacy_delete_user_files",
                "intervals_disconnect",
            }
            assert counts["prescribed_workouts"] == 1 and counts["training_blocks"] == 1
            assert await db.scalar(select(func.count()).select_from(Recommendation)) == 0
            assert await db.scalar(select(func.count()).select_from(Decision)) == 0
            await privacy.schedule_retention(db, now=now)
            await privacy.schedule_retention(db, now=now)
            await db.commit()
            assert await db.scalar(select(func.count()).select_from(Job).where(Job.kind == "privacy_retention")) == 1

    run(scenario())


def test_local_artifact_cleanup_is_effective_idempotent_and_rejects_traversal(private_api, tmp_path):
    api = private_api
    user_id, _ = api.identities[1]
    api.config.PRIVACY_STORAGE_ROOT = str(tmp_path)
    file = tmp_path / "synthetic.fit"
    file.write_bytes(b"synthetic-only")

    async def scenario():
        async with api.sessions() as db:
            artifact = await privacy_jobs.register_artifact(
                db, user_id=user_id, storage_kind="local", locator="synthetic.fit"
            )
            artifact.status = "delete_pending"
            job = Job(kind="privacy_delete_file", payload={"artifact_id": artifact.id})
            await privacy_jobs.delete_artifact(db, job)
            await db.commit()
            assert not file.exists() and await db.get(PrivacyArtifact, artifact.id) is None
            await privacy_jobs.delete_artifact(db, job)

    run(scenario())
    with pytest.raises(RuntimeError, match="Invalid"):
        privacy_jobs._delete_storage_object("local", "../outside.fit")


def test_admin_catalog_dates_capacity_suspension_and_manual_payment_idempotence(private_api):
    api = private_api
    admin_id, headers = api.identities[0]
    assert api.client.get("/api/v1/admin/commercial/catalog", headers=api.identities[1][1]).status_code == 403
    catalog = api.client.get("/api/v1/admin/commercial/catalog", headers=headers).json()
    org_id = catalog["organizations"][0]["id"]
    plan = api.client.post(
        "/api/v1/admin/commercial/plans",
        headers=headers,
        json={"name": "Synthetic plan", "athlete_limit": 1, "monthly_price_cents": 100, "currency": "MXN"},
    )
    assert plan.status_code == 201
    invalid = {
        "organization_id": org_id,
        "plan_id": plan.json()["id"],
        "starts_on": "2026-10-02",
        "ends_on": "2026-10-01",
    }
    assert api.client.post("/api/v1/admin/commercial/subscriptions", headers=headers, json=invalid).status_code == 422
    subscription = api.client.post(
        "/api/v1/admin/commercial/subscriptions",
        headers=headers,
        json={"organization_id": org_id, "plan_id": plan.json()["id"], "starts_on": date.today().isoformat()},
    )
    assert subscription.status_code == 201
    payment = {
        "subscription_id": subscription.json()["id"],
        "amount_cents": 100,
        "currency": "MXN",
        "paid_on": date.today().isoformat(),
        "reference": "synthetic-payment",
    }
    first = api.client.post("/api/v1/admin/commercial/payments", headers=headers, json=payment)
    repeated = api.client.post("/api/v1/admin/commercial/payments", headers=headers, json=payment)
    assert first.status_code == 201 and first.json() == repeated.json()
    assert (
        api.client.post(
            "/api/v1/admin/commercial/payments", headers=headers, json={**payment, "amount_cents": 200}
        ).status_code
        == 409
    )

    async def verify_capacity():
        async with api.sessions() as db:
            with pytest.raises(HTTPException) as error:
                await access.enforce_athlete_capacity(db, admin_id, org_id)
            assert error.value.status_code == 409

    run(verify_capacity())
    assert (
        api.client.patch(
            f"/api/v1/admin/organizations/{org_id}",
            headers=headers,
            json={"status": "suspended", "reason": "Synthetic test"},
        ).status_code
        == 200
    )

    async def verify_suspended():
        async with api.sessions() as db:
            with pytest.raises(HTTPException) as error:
                await access.require_organization_active(db, admin_id)
            assert error.value.status_code == 403

    run(verify_suspended())
    assert api.client.get("/api/v1/account/export", headers=headers).status_code == 200


def test_pywebpush_encrypts_payload_and_disables_redirects(private_api, monkeypatch):
    requests = pytest.importorskip("requests")
    pytest.importorskip("pywebpush")
    info = push_info()
    transmitted = []

    def post(_session, endpoint, **kwargs):
        transmitted.append(kwargs)
        response = requests.Response()
        response.status_code = 201
        return response

    monkeypatch.setattr(requests.Session, "post", post)
    assert notifications._send(info, "synthetic payload") == 201
    wire = transmitted[0]
    assert wire["allow_redirects"] is False and wire["timeout"] == 10
    assert b"synthetic payload" not in wire["data"]
    assert wire["headers"]["content-encoding"] == "aes128gcm"


def test_export_does_not_disclose_revoked_coach_recommendation_or_decision(private_api):
    api = private_api
    coach_id, headers = api.identities[0]
    athlete_id, _ = api.identities[1]

    async def scenario():
        async with api.sessions() as db:
            workout = PrescribedWorkout(
                athlete_id=athlete_id,
                coach_id=coach_id,
                title="Private revoked workout",
                scheduled_date=datetime.now(UTC),
            )
            coach = await db.get(User, coach_id)
            coach.is_superuser = False
            db.add(workout)
            await db.flush()
            recommendation = Recommendation(
                coach_id=coach_id,
                athlete_id=athlete_id,
                workout_id=workout.id,
                base_plan_version=1,
                changes={"title": "Private revoked recommendation"},
                rules_version="test",
                model_version="test",
            )
            db.add(recommendation)
            await db.flush()
            db.add(
                Decision(
                    recommendation_id=recommendation.id,
                    actor_id=coach_id,
                    action="reject",
                    note="Private revoked decision",
                    decided_at=datetime.now(UTC),
                )
            )
            assignment = await db.scalar(
                select(CoachAthleteAssignment).where(CoachAthleteAssignment.athlete_id == athlete_id)
            )
            assignment.status = "revoked"
            await db.commit()

    run(scenario())
    exported = api.client.get("/api/v1/account/export", headers=headers)
    assert exported.status_code == 200
    assert "Private revoked" not in exported.text


def test_capacity_is_serialized_between_coaches_in_postgres(private_api):
    if private_api.sessions.kw["bind"].dialect.name != "postgresql":
        pytest.skip("Capacity race requires PostgreSQL row locks")
    api = private_api
    coach_id, _ = api.identities[0]
    first_candidate = api.identities[2][0]

    async def scenario():
        async with api.sessions() as db:
            org = await db.scalar(select(Organization))
            plan = CommercialPlan(name="Race plan", athlete_limit=2)
            db.add(plan)
            await db.flush()
            db.add(Subscription(organization_id=org.id, plan_id=plan.id, status="active", starts_on=date.today()))
            other = User(
                email="race-candidate@example.com",
                first_name="Race",
                last_name="Synthetic",
                timezone="UTC",
                role="athlete",
                hashed_password=hash_password("Synthetic-test-password"),
            )
            db.add(other)
            await db.flush()
            other_id, org_id = other.id, org.id
            await db.commit()

        async def reserve(athlete_id):
            async with api.sessions() as db:
                try:
                    await access.enforce_athlete_capacity(db, coach_id, org_id)
                except HTTPException as error:
                    await db.rollback()
                    return error.status_code
                db.add(
                    CoachAthleteAssignment(
                        organization_id=org_id, coach_id=coach_id, athlete_id=athlete_id, status="active"
                    )
                )
                await db.commit()
                return 201

        assert sorted(await asyncio.gather(reserve(first_candidate), reserve(other_id))) == [201, 409]
        async with api.sessions() as db:
            assert (
                await db.scalar(
                    select(func.count(func.distinct(CoachAthleteAssignment.athlete_id))).where(
                        CoachAthleteAssignment.organization_id == org_id, CoachAthleteAssignment.status == "active"
                    )
                )
                == 2
            )

    run(scenario())


def test_active_second_organization_cannot_bypass_suspended_assignment(private_api):
    api = private_api
    coach_id, _ = api.identities[0]
    athlete_id, _ = api.identities[1]

    async def scenario():
        async with api.sessions() as db:
            coach = await db.get(User, coach_id)
            coach.is_superuser = False
            organization = await db.scalar(select(Organization))
            organization.status = "suspended"
            active = Organization(name="Unrelated active organization", slug="unrelated-synthetic", status="active")
            db.add(active)
            await db.flush()
            db.add(OrganizationMembership(organization_id=active.id, user_id=coach_id, role="owner", status="active"))
            await db.commit()
            with pytest.raises(HTTPException) as error:
                await access.require_athlete_access(db, coach, athlete_id)
            assert error.value.status_code == 403

    run(scenario())


def test_withdrawn_athlete_can_export_prior_own_chat_but_not_resume_processing(private_api):
    api = private_api
    user_id, headers = api.identities[1]

    async def scenario():
        async with api.sessions() as db:
            thread = AssistantThread(owner_id=user_id, role="athlete", athlete_scope_id=user_id, title="Own context")
            db.add(thread)
            await db.flush()
            db.add(
                AssistantMessage(
                    thread_id=thread.id,
                    author="assistant",
                    content="Synthetic prior personal context",
                    created_at=datetime.now(UTC),
                    citations=[{"athlete_id": user_id}],
                )
            )
            await db.commit()

    run(scenario())
    consent = api.client.post(
        "/api/v1/consents", headers=headers, json={"scope": "training_data_processing", "version": "pilot-v1"}
    )
    assert consent.status_code == 201
    assert api.client.delete(f"/api/v1/consents/{consent.json()['id']}", headers=headers).status_code == 204
    export = api.client.get("/api/v1/account/export", headers=headers)
    assert export.status_code == 200 and "Synthetic prior personal context" in export.text
    assert (
        api.client.get(
            f"/api/v1/athletes/{user_id}/profile", headers=headers
        ).status_code
        == 403
    )
