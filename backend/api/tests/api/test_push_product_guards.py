import asyncio
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select, update
from test_privacy_notifications import enable_push, run
from test_privacy_notifications import private_api as _private_api

from app.infrastructure.database.models import PrescribedWorkout, User
from app.infrastructure.database.models.privacy import NotificationDelivery, NotificationPreference
from app.infrastructure.database.models.product import (
    AthleteConnection,
    CoachAthleteAssignment,
    CommercialPlan,
    Complaint,
    Consent,
    Job,
    Organization,
    OrganizationMembership,
    Subscription,
    UserRoleAssignment,
)
from app.services import notifications, product_notifications
from app.services.notifications import PushDeferred, send_notification
from app.services.product_notifications import dispatch_product_notification, queue_product_event


@pytest.fixture(params=["sqlite", "postgres"])
def private_api(request, monkeypatch):
    yield from _private_api.__wrapped__(request, monkeypatch)


async def prepare_push(api, *, source_kind="complaint", recipient_index=0):
    coach_id = api.identities[recipient_index][0]
    athlete_id = api.identities[1][0]
    async with api.sessions() as db:
        organization = await db.scalar(select(Organization))
        if recipient_index != 0:
            db.add(UserRoleAssignment(user_id=coach_id, role="coach"))
            db.add(OrganizationMembership(user_id=coach_id, organization_id=organization.id, role="coach"))
            db.add(CoachAthleteAssignment(coach_id=coach_id, athlete_id=athlete_id, organization_id=organization.id))
        consent = Consent(
            user_id=athlete_id, scope="training_data_processing", version="pilot-v1", granted_at=datetime.now(UTC)
        )
        db.add(consent)
        plan = CommercialPlan(name="Synthetic Push guard", athlete_limit=10)
        db.add(plan)
        await db.flush()
        subscription = Subscription(
            organization_id=organization.id, plan_id=plan.id, status="active", starts_on=date(2026, 1, 1)
        )
        db.add(subscription)
        if source_kind == "workout":
            source = PrescribedWorkout(
                athlete_id=athlete_id,
                coach_id=coach_id,
                title="Synthetic source",
                sport_type="running",
                scheduled_date=datetime.now(UTC) + timedelta(hours=1),
                status="published",
                version=1,
                steps=[],
            )
            entity = "workout"
        elif source_kind == "connection":
            source = AthleteConnection(athlete_id=athlete_id, provider="intervals_icu", status="error")
            entity = "connection"
        else:
            source = Complaint(
                athlete_id=athlete_id,
                zone="synthetic",
                laterality="center",
                started_on=date(2026, 9, 30),
                intensity_0_10=3,
                limits_movement=False,
                status="reported",
                version=1,
            )
            entity = "complaint"
        db.add(source)
        await db.flush()
        category = "sync" if entity == "connection" else "review"
        await queue_product_event(
            db,
            recipient_id=coach_id,
            athlete_id=athlete_id,
            category=category,
            event_key=f"guard:{entity}:{source.id}",
            entity=entity,
            entity_id=source.id,
            entity_version=getattr(source, "version", None),
        )
        await db.commit()
        await db.execute(
            update(NotificationPreference)
            .where(NotificationPreference.user_id == coach_id)
            .values(categories=["plan", "review", "sync"])
        )
        event = await db.scalar(select(Job).where(Job.kind == "product_notification"))
        assert await dispatch_product_notification(db, event)
        await db.commit()
        job = await db.scalar(select(Job).where(Job.kind == "send_web_push"))
        assert job is not None and job.payload["product_source"]["athlete_id"] == athlete_id
        return {
            "job_id": job.id,
            "consent_id": consent.id,
            "organization_id": organization.id,
            "subscription_id": subscription.id,
            "source_id": source.id,
            "athlete_id": athlete_id,
            "coach_id": coach_id,
        }


@pytest.mark.parametrize(
    "change",
    [
        "training",
        "assignment",
        "organization",
        "subscription",
        "complaint_closed",
        "workout_version",
        "connection_recovered",
        "none",
    ],
)
def test_source_is_revalidated_after_product_dispatch(private_api, change):
    api = private_api
    enable_push(api, 0)
    source_kind = (
        "workout" if change == "workout_version" else "connection" if change == "connection_recovered" else "complaint"
    )

    async def scenario():
        ids = await prepare_push(api, source_kind=source_kind)
        async with api.sessions() as sender:
            # Hold ORM instances alive across another transaction to reproduce a
            # worker session which handled an earlier job before the withdrawal.
            old_consent = await sender.get(Consent, ids["consent_id"])
            old_organization = await sender.get(Organization, ids["organization_id"])
            old_subscription = await sender.get(Subscription, ids["subscription_id"])
            await sender.commit()
            async with api.sessions() as changed:
                if change == "training":
                    await changed.execute(
                        update(Consent).where(Consent.id == ids["consent_id"]).values(revoked_at=datetime.now(UTC))
                    )
                elif change == "assignment":
                    await changed.execute(
                        update(CoachAthleteAssignment)
                        .where(CoachAthleteAssignment.coach_id == ids["coach_id"])
                        .values(status="revoked")
                    )
                elif change == "organization":
                    await changed.execute(
                        update(Organization).where(Organization.id == ids["organization_id"]).values(status="suspended")
                    )
                elif change == "subscription":
                    await changed.execute(
                        update(Subscription).where(Subscription.id == ids["subscription_id"]).values(status="suspended")
                    )
                elif change == "complaint_closed":
                    await changed.execute(
                        update(Complaint).where(Complaint.id == ids["source_id"]).values(status="closed")
                    )
                elif change == "workout_version":
                    await changed.execute(
                        update(PrescribedWorkout).where(PrescribedWorkout.id == ids["source_id"]).values(version=2)
                    )
                elif change == "connection_recovered":
                    await changed.execute(
                        update(AthleteConnection)
                        .where(AthleteConnection.id == ids["source_id"])
                        .values(status="connected")
                    )
                await changed.commit()
            job = await sender.get(Job, ids["job_id"])
            transports = []
            await send_notification(sender, job, transport=lambda *args: transports.append(args) or 201)
            await sender.commit()
            delivery = await sender.get(NotificationDelivery, job.payload["delivery_id"])
            assert delivery.status == ("delivered" if change == "none" else "cancelled")
            assert len(transports) == (1 if change == "none" else 0)
            assert old_consent is not None and old_organization is not None and old_subscription is not None

    run(scenario())


@pytest.mark.parametrize("busy_source", ["athlete", "organization", "subscription"])
def test_contended_source_defers_without_reversing_actor_locks(private_api, busy_source):
    api = private_api
    if api.sessions.kw["bind"].dialect.name != "postgresql":
        pytest.skip("NOWAIT and savepoint recovery require real PostgreSQL")
    enable_push(api, 2)

    async def scenario():
        ids = await prepare_push(api, recipient_index=2)
        assert ids["coach_id"] > ids["athlete_id"]
        async with api.sessions() as actor, api.sessions() as sender:
            model, identifier = {
                "athlete": (User, ids["athlete_id"]),
                "organization": (Organization, ids["organization_id"]),
                "subscription": (Subscription, ids["subscription_id"]),
            }[busy_source]
            await actor.scalar(select(model).where(model.id == identifier).with_for_update())
            job = await sender.get(Job, ids["job_id"])
            before = datetime.now(UTC)
            transports = []
            with pytest.raises(PushDeferred):
                await asyncio.wait_for(
                    send_notification(sender, job, transport=lambda *args: transports.append(args) or 201, now=before),
                    timeout=2,
                )
            assert not transports and job.run_after == before + timedelta(seconds=5)
            assert (await sender.get(NotificationDelivery, job.payload["delivery_id"])).status == "queued"
            await sender.commit()  # The savepoint recovered; the deferred job can commit.
            # An API actor can take the recipient after deferral without a cycle.
            await asyncio.wait_for(
                actor.scalar(select(User.id).where(User.id == ids["coach_id"]).with_for_update()), timeout=2
            )
            await actor.execute(
                update(Consent).where(Consent.id == ids["consent_id"]).values(revoked_at=datetime.now(UTC))
            )
            await actor.commit()
            await send_notification(sender, job, transport=lambda *args: transports.append(args) or 201)
            await sender.commit()
            assert not transports
            assert (await sender.get(NotificationDelivery, job.payload["delivery_id"])).status == "cancelled"

    run(scenario())


@pytest.mark.parametrize("delay_stage", ["source_validation", "thread_pool"])
def test_deadline_is_rechecked_after_waiting(private_api, monkeypatch, delay_stage):
    api = private_api
    enable_push(api, 0)
    clock = [datetime.now(UTC)]

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock[0].astimezone(tz) if tz else clock[0].replace(tzinfo=None)

    async def scenario():
        ids = await prepare_push(api)
        monkeypatch.setattr(notifications, "datetime", Clock)
        if delay_stage == "source_validation":
            original = product_notifications.source_is_current

            async def delayed_source(*args):
                result = await original(*args)
                clock[0] += timedelta(seconds=2)
                return result

            monkeypatch.setattr(product_notifications, "source_is_current", delayed_source)
        else:

            async def delayed_thread(function, *args):
                clock[0] += timedelta(seconds=2)
                return function(*args)

            monkeypatch.setattr(notifications.asyncio, "to_thread", delayed_thread)
        async with api.sessions() as db:
            job = await db.get(Job, ids["job_id"])
            job.payload = {**job.payload, "valid_until": (clock[0] + timedelta(seconds=1)).isoformat()}
            transports = []
            await send_notification(db, job, transport=lambda *args: transports.append(args) or 201)
            await db.commit()
            assert not transports
            assert (await db.get(NotificationDelivery, job.payload["delivery_id"])).status == "cancelled"

    run(scenario())
