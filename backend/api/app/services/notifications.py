"""Encrypted Web Push subscriptions and a minimal, consent-checked durable outbox."""

import asyncio
import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.infrastructure.database.models import User
from app.infrastructure.database.models.privacy import NotificationDelivery, NotificationPreference, PushSubscription
from app.infrastructure.database.models.product import CoachAthleteAssignment, Consent, Job, Organization, Subscription

CATEGORIES = {"plan", "reminder", "review", "sync"}
DEFAULT_PUSH_HOSTS = "fcm.googleapis.com,updates.push.services.mozilla.com,web.push.apple.com"


def push_cipher() -> Fernet:
    try:
        return Fernet(getattr(settings, "PUSH_ENCRYPTION_KEY", "").encode())
    except (TypeError, ValueError) as exc:
        raise HTTPException(503, "PUSH_CONFIGURATION_REQUIRED") from exc


def push_ready() -> bool:
    if not all(
        getattr(settings, key, "") for key in ("WEB_PUSH_PUBLIC_KEY", "WEB_PUSH_PRIVATE_KEY", "WEB_PUSH_CONTACT")
    ):
        return False
    if not getattr(settings, "WEB_PUSH_CONTACT", "").startswith(("mailto:", "https://")):
        return False
    try:
        push_cipher()
    except HTTPException:
        return False
    return True


def validate_subscription(info: dict) -> None:
    approved = {
        host.strip().lower()
        for host in getattr(settings, "PUSH_ENDPOINT_HOSTS", DEFAULT_PUSH_HOSTS).split(",")
        if host.strip()
    }
    try:
        endpoint = urlsplit(info["endpoint"])
        valid_endpoint = (
            endpoint.scheme == "https"
            and endpoint.hostname in approved
            and endpoint.port in (None, 443)
            and not endpoint.username
            and not endpoint.password
            and not endpoint.fragment
        )
    except ValueError:
        valid_endpoint = False
    if not valid_endpoint:
        raise HTTPException(422, "Endpoint Push no autorizado")
    try:
        auth = base64.b64decode(
            info["keys"]["auth"] + "=" * (-len(info["keys"]["auth"]) % 4), altchars=b"-_", validate=True
        )
        public = base64.b64decode(
            info["keys"]["p256dh"] + "=" * (-len(info["keys"]["p256dh"]) % 4), altchars=b"-_", validate=True
        )
        if len(auth) != 16 or len(public) != 65:
            raise ValueError("key size")
        ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), public)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(422, "Claves Push inválidas") from exc


def aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def next_allowed(preference: NotificationPreference, now: datetime) -> datetime:
    if not preference.quiet_start or preference.quiet_start == preference.quiet_end:
        return now
    local = now.astimezone(ZoneInfo(preference.timezone))
    start = tuple(map(int, preference.quiet_start.split(":")))
    end = tuple(map(int, preference.quiet_end.split(":")))
    clock = (local.hour, local.minute)
    quiet = start <= clock < end if start < end else clock >= start or clock < end
    if not quiet:
        return now
    day = local.date() + timedelta(days=1 if start > end and clock >= start else 0)
    return datetime(day.year, day.month, day.day, end[0], end[1], tzinfo=ZoneInfo(preference.timezone)).astimezone(UTC)


async def explicit_push_consent(db: AsyncSession, user_id: int) -> bool:
    row = await db.scalar(
        select(Consent)
        .where(Consent.user_id == user_id, Consent.scope == "web_push", Consent.version == "pilot-v1")
        .order_by(Consent.granted_at.desc(), Consent.id.desc())
        .limit(1)
    )
    return row is not None and row.revoked_at is None


async def register_subscription(db: AsyncSession, user: User, info: dict) -> PushSubscription:
    if not push_ready():
        raise HTTPException(503, "PUSH_CONFIGURATION_REQUIRED")
    await db.scalar(select(User.id).where(User.id == user.id).with_for_update())
    if not await explicit_push_consent(db, user.id):
        raise HTTPException(403, "CONSENT_REQUIRED:web_push")
    validate_subscription(info)
    digest = hashlib.sha256(info["endpoint"].encode()).hexdigest()
    subscription = await db.scalar(
        select(PushSubscription).where(PushSubscription.endpoint_hash == digest).with_for_update()
    )
    if subscription is not None and subscription.user_id != user.id:
        # Endpoints are capability secrets; an authenticated stranger cannot transfer one.
        raise HTTPException(409, "Este dispositivo debe darse de baja de la cuenta anterior")
    if subscription is None:
        subscription = PushSubscription(user_id=user.id, endpoint_hash=digest)
        db.add(subscription)
    expiry = info.get("expirationTime")
    if expiry and datetime.fromtimestamp(expiry / 1000, UTC) <= datetime.now(UTC):
        raise HTTPException(422, "La suscripción ya expiró")
    subscription.subscription_enc = (
        push_cipher().encrypt(json.dumps({"endpoint": info["endpoint"], "keys": info["keys"]}).encode()).decode()
    )
    subscription.revoked_at = None
    subscription.expires_at = datetime.fromtimestamp(expiry / 1000, UTC) if expiry else None
    await db.flush()
    return subscription


async def queue_notification(
    db: AsyncSession, *, user_id: int, category: str, event_key: str, now: datetime | None = None
) -> int:
    if category not in CATEGORIES:
        raise ValueError("Categoría de notificación inválida")
    now = now or datetime.now(UTC)
    user = await db.scalar(select(User).where(User.id == user_id).with_for_update())
    preference = await db.get(NotificationPreference, user_id)
    if (
        user is None
        or user.deleted_at
        or not preference
        or not preference.enabled
        or category not in preference.categories
        or not await explicit_push_consent(db, user_id)
    ):
        return 0
    # Exactly one persisted delivery per event and device; no athlete facts in payload.
    digest = hashlib.sha256(f"{category}:{event_key}".encode()).hexdigest()
    subscriptions = (
        await db.scalars(
            select(PushSubscription).where(
                PushSubscription.user_id == user_id,
                PushSubscription.revoked_at.is_(None),
                PushSubscription.subscription_enc.is_not(None),
            )
        )
    ).all()
    queued = 0
    for subscription in subscriptions:
        if subscription.expires_at and aware(subscription.expires_at) <= now:
            subscription.revoked_at, subscription.subscription_enc = now, None
            continue
        exists = await db.scalar(
            select(NotificationDelivery.id).where(
                NotificationDelivery.subscription_id == subscription.id, NotificationDelivery.event_hash == digest
            )
        )
        if exists:
            continue
        delivery = NotificationDelivery(
            user_id=user_id, subscription_id=subscription.id, category=category, event_hash=digest, status="queued"
        )
        db.add(delivery)
        await db.flush()
        db.add(
            Job(
                kind="send_web_push",
                payload={"delivery_id": delivery.id},
                run_after=next_allowed(preference, now),
                max_attempts=settings.JOB_MAX_ATTEMPTS,
                dedupe_key=f"webpush:{delivery.id}",
            )
        )
        queued += 1
    return queued


class PushDeferred(Exception):
    """Worker must retain run_after/status=pending and undo the lease attempt."""


def _send(info: dict, payload: str) -> int:
    from pywebpush import WebPushException, webpush
    from requests import Session

    class NoRedirectSession(Session):
        def post(self, *args, **kwargs):
            # Never forward a VAPID authorization or endpoint capability on redirects.
            kwargs["allow_redirects"] = False
            return super().post(*args, **kwargs)

    try:
        with NoRedirectSession() as session:
            response = webpush(
                subscription_info=info,
                data=payload,
                vapid_private_key=getattr(settings, "WEB_PUSH_PRIVATE_KEY", ""),
                vapid_claims={"sub": getattr(settings, "WEB_PUSH_CONTACT", "")},
                timeout=10,
                ttl=getattr(settings, "WEB_PUSH_TTL_SECONDS", 3600),
                verbose=False,
                requests_session=session,
                headers={"Urgency": "normal"},
            )
        return response.status_code
    except WebPushException as exc:
        # Provider exception text can contain endpoint/body. Only propagate the status.
        return exc.response.status_code if exc.response is not None else 503
    except Exception:
        raise RuntimeError("Push transport unavailable") from None


async def lock_product_source(db: AsyncSession, job: Job, user: User, source: dict, now: datetime) -> None:
    """Serialize withdrawal/suspension without reversing API actor→athlete locks.

    The recipient is already locked. Contended source locks use NOWAIT inside a
    savepoint: release the failed attempt and defer before any provider traffic.
    """
    athlete_id = source["athlete_id"]
    if athlete_id == user.id:
        return
    try:
        async with db.begin_nested():
            await db.scalar(select(User.id).where(User.id == athlete_id).with_for_update(nowait=True))
            organization_id = await db.scalar(
                select(CoachAthleteAssignment.organization_id).where(
                    CoachAthleteAssignment.coach_id == user.id,
                    CoachAthleteAssignment.athlete_id == athlete_id,
                    CoachAthleteAssignment.status == "active",
                )
            )
            if organization_id is not None:
                await db.scalar(
                    select(Organization.id).where(Organization.id == organization_id).with_for_update(nowait=True)
                )
                await db.scalar(
                    select(Subscription.id)
                    .where(Subscription.organization_id == organization_id)
                    .with_for_update(nowait=True)
                )
    except DBAPIError as exc:
        if getattr(exc.orig, "sqlstate", None) != "55P03" and getattr(exc.orig, "pgcode", None) != "55P03":
            raise
        job.run_after = now + timedelta(seconds=5)
        raise PushDeferred() from None


async def send_notification(db: AsyncSession, job: Job, *, transport=None, now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    delivery = await db.get(NotificationDelivery, job.payload["delivery_id"])
    if not delivery or delivery.status != "queued":
        return
    user = await db.scalar(
        select(User).where(User.id == delivery.user_id).with_for_update().execution_options(populate_existing=True)
    )
    # The row was read before waiting on the owner's lock. Refresh it so a
    # withdrawal/regrant or erasure cannot revive an old cached queued delivery.
    delivery = await db.scalar(
        select(NotificationDelivery)
        .where(NotificationDelivery.id == delivery.id)
        .execution_options(populate_existing=True)
    )
    if not delivery or delivery.status != "queued":
        return
    sub = await db.scalar(
        select(PushSubscription)
        .where(PushSubscription.id == delivery.subscription_id)
        .execution_options(populate_existing=True)
    )
    preference = await db.scalar(
        select(NotificationPreference)
        .where(NotificationPreference.user_id == delivery.user_id)
        .execution_options(populate_existing=True)
    )
    if (
        not user
        or user.deleted_at
        or not sub
        or sub.revoked_at
        or not sub.subscription_enc
        or not preference
        or not preference.enabled
        or delivery.category not in preference.categories
        or not await explicit_push_consent(db, delivery.user_id)
    ):
        delivery.status = "cancelled"
        return
    if sub.expires_at and aware(sub.expires_at) <= now:
        sub.revoked_at, sub.subscription_enc, delivery.status = now, None, "expired"
        return
    if "product_source" in job.payload:
        source = job.payload["product_source"]
        athlete_id = source.get("athlete_id") if isinstance(source, dict) else None
        if (
            not isinstance(athlete_id, int)
            or isinstance(athlete_id, bool)
            or athlete_id < 1
            or source.get("recipient_id") != user.id
            or source.get("category") != delivery.category
        ):
            delivery.status = "cancelled"
            return
        await lock_product_source(db, job, user, source, now)
        from app.services.product_notifications import source_is_current

        if not await source_is_current(db, source, user, now):
            delivery.status = "cancelled"
            return
    deadline = None
    if "valid_until" in job.payload:
        try:
            deadline = datetime.fromisoformat(job.payload["valid_until"].replace("Z", "+00:00"))
            if deadline.tzinfo is None:
                raise ValueError("A deadline needs an explicit timezone")
        except (AttributeError, TypeError, ValueError):
            delivery.status = "cancelled"
            return
        if now >= deadline:
            delivery.status = "cancelled"
            return
    next_time = next_allowed(preference, now)
    if deadline is not None and next_time >= deadline:
        delivery.status = "cancelled"
        return
    if next_time > now:
        job.run_after = next_time
        raise PushDeferred()
    if not push_ready():
        raise RuntimeError("Push configuration unavailable")
    try:
        info = json.loads(push_cipher().decrypt(sub.subscription_enc.encode()))
        validate_subscription(info)
    except Exception:
        raise RuntimeError("Push subscription unavailable") from None
    payload = json.dumps(
        {
            "title": "NODO",
            "body": "Tienes una actualización. Abre NODO para revisarla.",
            "url": "/app",
            "tag": f"nodo-{delivery.event_hash[:24]}",
        }
    )
    # The lock orders successful revocation after in-flight delivery; subsequent jobs see it.
    status = await asyncio.to_thread(transport or _send, info, payload)
    if status in (404, 410):
        sub.subscription_enc, sub.revoked_at, delivery.status = None, now, "expired"
    elif 200 <= status < 300:
        delivery.status, delivery.delivered_at = "delivered", now
    elif status == 429 or status >= 500:
        raise RuntimeError(f"Push retryable HTTP {status}")
    else:
        delivery.status = "rejected"
