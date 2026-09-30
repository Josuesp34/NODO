"""Transactional product events. Recipients are locked only by the separate worker dispatch."""

import hashlib
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.core.config import settings
from app.infrastructure.database.models import PrescribedWorkout, User
from app.infrastructure.database.models.product import (
    AthleteConnection,
    CoachAthleteAssignment,
    Complaint,
    Job,
    Recommendation,
    UserRoleAssignment,
)
from app.services.access import require_organization_active, require_role
from app.services.notifications import aware, next_allowed, queue_notification
from app.services.privacy import require_processing_consent

EVENT_KIND = "product_notification"


async def queue_product_event(
    db,
    *,
    recipient_id: int,
    athlete_id: int,
    category: str,
    event_key: str,
    entity: str,
    entity_id: int,
    entity_version: int | None = None,
    valid_until: datetime | None = None,
    now: datetime | None = None,
) -> bool:
    """No recipient lock or commit here: persist together with the triggering business mutation."""
    now = now or datetime.now(UTC)
    digest = hashlib.sha256(f"{recipient_id}:{category}:{event_key}".encode()).hexdigest()
    key = f"product-push:{digest}"
    payload = {
        "recipient_id": recipient_id,
        "athlete_id": athlete_id,
        "category": category,
        "event_key": event_key,
        "entity": entity,
        "entity_id": entity_id,
        "entity_version": entity_version,
    }
    if valid_until is not None:
        payload["valid_until"] = aware(valid_until).isoformat()
    dialect = db.get_bind().dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        raise RuntimeError("Outbox requiere PostgreSQL o SQLite de prueba")
    insert = pg_insert if dialect == "postgresql" else sqlite_insert
    # Native conflict handling preserves the outer transaction, including on
    # SQLite where a SAVEPOINT after a read can otherwise commit before rollback.
    result = await db.execute(
        insert(Job)
        .values(kind=EVENT_KIND, payload=payload, dedupe_key=key, run_after=now, max_attempts=settings.JOB_MAX_ATTEMPTS)
        .on_conflict_do_nothing(index_elements=[Job.dedupe_key])
        .returning(Job.id)
    )
    return result.scalar_one_or_none() is not None


async def notify_assigned_coaches(db, *, athlete_id, category, event_key, entity, entity_id, entity_version=None):
    recipients = (
        await db.scalars(
            select(CoachAthleteAssignment.coach_id)
            .where(CoachAthleteAssignment.athlete_id == athlete_id, CoachAthleteAssignment.status == "active")
            .distinct()
            .order_by(CoachAthleteAssignment.coach_id)
        )
    ).all()
    for recipient_id in recipients:
        await queue_product_event(
            db,
            recipient_id=recipient_id,
            athlete_id=athlete_id,
            category=category,
            event_key=event_key,
            entity=entity,
            entity_id=entity_id,
            entity_version=entity_version,
        )


async def notify_sync_problem(db, *, athlete_id: int, connection_id: int, episode_key: str) -> None:
    """Hook for Intervals before committing reconnect_required; no provider traffic here."""
    args = {
        "athlete_id": athlete_id,
        "category": "sync",
        "event_key": f"sync-problem:{connection_id}:{episode_key}",
        "entity": "connection",
        "entity_id": connection_id,
    }
    await queue_product_event(db, recipient_id=athlete_id, **args)
    await notify_assigned_coaches(db, **args)


async def source_is_current(db, payload, user, now):
    athlete_id = payload["athlete_id"]
    athlete = await db.scalar(select(User).where(User.id == athlete_id).execution_options(populate_existing=True))
    if athlete is None or athlete.deleted_at:
        return False
    try:
        await require_processing_consent(db, athlete_id, "training_data_processing")
        if user.id != athlete_id:
            assignment = await db.scalar(
                select(CoachAthleteAssignment)
                .where(
                    CoachAthleteAssignment.coach_id == user.id,
                    CoachAthleteAssignment.athlete_id == athlete_id,
                    CoachAthleteAssignment.status == "active",
                )
                .execution_options(populate_existing=True)
            )
            if assignment is None:
                return False
            await require_role(db, user, "coach")
            await require_organization_active(db, user.id, organization_id=assignment.organization_id)
        else:
            assigned = await db.scalar(
                select(UserRoleAssignment.id).where(
                    UserRoleAssignment.user_id == user.id, UserRoleAssignment.role == "athlete"
                )
            )
            if assigned is None:
                return False
    except HTTPException:
        return False
    entity, identifier = payload["entity"], payload["entity_id"]
    if entity == "workout":
        row = await db.scalar(
            select(PrescribedWorkout)
            .where(PrescribedWorkout.id == identifier)
            .execution_options(populate_existing=True)
        )
        return (
            row is not None
            and row.athlete_id == athlete_id
            and row.status == "published"
            and row.version == payload["entity_version"]
            and (payload["category"] != "reminder" or aware(row.scheduled_date) > now)
        )
    if entity == "complaint":
        row = await db.scalar(
            select(Complaint).where(Complaint.id == identifier).execution_options(populate_existing=True)
        )
        return (
            row is not None
            and row.athlete_id == athlete_id
            and row.version == payload["entity_version"]
            and row.status != "closed"
        )
    if entity == "recommendation":
        row = await db.scalar(
            select(Recommendation).where(Recommendation.id == identifier).execution_options(populate_existing=True)
        )
        return row is not None and row.athlete_id == athlete_id and row.coach_id == user.id and row.status == "pending"
    if entity == "connection":
        row = await db.scalar(
            select(AthleteConnection)
            .where(AthleteConnection.id == identifier)
            .execution_options(populate_existing=True)
        )
        return row is not None and row.athlete_id == athlete_id and row.status in {"reconnect_required", "error"}
    return False


async def dispatch_product_notification(db, job, *, now: datetime | None = None) -> bool:
    """One recipient per job avoids cross-user lock ordering; worker owns its final CAS/commit."""
    if job.kind != EVENT_KIND:
        return False
    now = now or datetime.now(UTC)
    payload = job.payload
    user = await db.scalar(
        select(User)
        .where(User.id == payload["recipient_id"])
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    try:
        deadline = datetime.fromisoformat(payload["valid_until"]) if payload.get("valid_until") else None
    except (TypeError, ValueError):
        job.payload = {"queued_devices": 0, "skipped": "invalid_deadline"}
        return True
    if deadline is not None and (deadline.tzinfo is None or deadline <= now):
        job.payload = {"queued_devices": 0, "skipped": "expired"}
        return True
    if user is None or user.deleted_at or not await source_is_current(db, payload, user, now):
        job.payload = {"queued_devices": 0, "skipped": "source_unavailable"}
        return True
    from app.infrastructure.database.models.privacy import NotificationPreference

    preference = await db.scalar(
        select(NotificationPreference)
        .where(NotificationPreference.user_id == user.id)
        .execution_options(populate_existing=True)
    )
    if deadline and preference and next_allowed(preference, now) >= deadline:
        job.payload = {"queued_devices": 0, "skipped": "quiet_hours_after_deadline"}
        return True
    count = await queue_notification(
        db, user_id=user.id, category=payload["category"], event_key=payload["event_key"], now=now
    )
    if count:
        # The delivery handler rechecks the source and deadline before contacting Push.
        from app.infrastructure.database.models.privacy import NotificationDelivery

        digest = hashlib.sha256(f"{payload['category']}:{payload['event_key']}".encode()).hexdigest()
        deliveries = (
            await db.scalars(
                select(NotificationDelivery.id).where(
                    NotificationDelivery.user_id == user.id, NotificationDelivery.event_hash == digest
                )
            )
        ).all()
        await db.flush()
        rows = (
            await db.scalars(
                select(Job).where(Job.dedupe_key.in_([f"webpush:{identifier}" for identifier in deliveries]))
            )
        ).all()
        for row in rows:
            if row.payload.get("delivery_id") in deliveries:
                row.payload = {**row.payload, "product_source": payload}
                if deadline:
                    row.payload = {**row.payload, "valid_until": deadline.isoformat()}
    job.payload = {"queued_devices": count}
    return True
