"""Local worker scheduler: opt-in reminder, once per published workout/version."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.infrastructure.database.models import PrescribedWorkout, User
from app.infrastructure.database.models.privacy import NotificationPreference
from app.services.notifications import aware, explicit_push_consent, next_allowed
from app.services.product_notifications import queue_product_event


async def schedule_workout_reminders(db, *, now: datetime | None = None) -> int:
    """Call before claim_jobs in run_once; caller commits. No external scheduler or provider needed."""
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError("El scheduler requiere hora con zona")
    upcoming = (
        await db.execute(
            select(PrescribedWorkout, NotificationPreference)
            .join(User, User.id == PrescribedWorkout.athlete_id)
            .join(NotificationPreference, NotificationPreference.user_id == User.id)
            .where(
                PrescribedWorkout.status == "published",
                PrescribedWorkout.scheduled_date > now,
                PrescribedWorkout.scheduled_date <= now + timedelta(hours=1),
                NotificationPreference.enabled.is_(True),
                User.deleted_at.is_(None),
            )
            .order_by(PrescribedWorkout.scheduled_date, PrescribedWorkout.id)
        )
    ).all()
    queued = 0
    for workout, preference in upcoming:
        if "reminder" not in preference.categories or not await explicit_push_consent(db, workout.athlete_id):
            continue
        start = aware(workout.scheduled_date)
        if next_allowed(preference, now) >= start:
            continue
        local_day = start.astimezone(ZoneInfo(preference.timezone)).date()
        queued += int(
            await queue_product_event(
                db,
                recipient_id=workout.athlete_id,
                athlete_id=workout.athlete_id,
                category="reminder",
                event_key=f"workout-reminder:{workout.id}:{workout.version}:{local_day}",
                entity="workout",
                entity_id=workout.id,
                entity_version=workout.version,
                valid_until=start,
                now=now,
            )
        )
    return queued
