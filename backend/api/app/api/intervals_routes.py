import json
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode, urlparse

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import current_session, current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.security import token_hash
from app.infrastructure.database.models import AuthSession, User
from app.infrastructure.database.models.product import AthleteConnection, IngestionEvent, Job
from app.infrastructure.database.models.providers import ProviderOAuthState
from app.services.access import require_athlete_access, require_role
from app.services.audit import add_audit
from app.services.intervals_real import (
    PROVIDER,
    SCOPES,
    IntervalsError,
    RealIntervalsAdapter,
    cipher,
    digest,
    enqueue_sync,
    external_id,
    queue_remote_disconnect,
)
from app.services.provider_policy import require_provider_consent

router = APIRouter(tags=["Intervals OAuth"])


class Callback(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state: str = Field(min_length=30, max_length=200)
    code: str | None = Field(default=None, max_length=500)
    error: str | None = Field(default=None, max_length=80)


async def own_athlete(db, user, athlete_id):
    await require_athlete_access(db, user, athlete_id)
    if user.id != athlete_id:
        raise HTTPException(403, "El atleta autoriza su propia conexión")
    await require_role(db, user, "athlete")
    await require_provider_consent(db, athlete_id, "training_data_processing")


def configured():
    uri = urlparse(settings.INTERVALS_REDIRECT_URI)
    if not settings.INTERVALS_CLIENT_ID or not settings.INTERVALS_CLIENT_SECRET or not uri.hostname:
        raise HTTPException(503, "INTERVALS_CONFIGURATION_REQUIRED")
    if uri.scheme != "https" and not (
        settings.ENVIRONMENT == "development" and uri.hostname in {"localhost", "127.0.0.1"}
    ):
        raise HTTPException(503, "INTERVALS_REDIRECT_CONFIGURATION_REQUIRED")
    cipher()


@router.post("/connections/intervals/{athlete_id}/authorize")
async def authorize(
    athlete_id: int,
    user: User = Depends(current_user),
    session: AuthSession = Depends(current_session),
    db: AsyncSession = Depends(get_db),
):
    await own_athlete(db, user, athlete_id)
    configured()
    state = secrets.token_urlsafe(40)
    db.add(
        ProviderOAuthState(
            user_id=user.id,
            athlete_id=athlete_id,
            session_id=session.id,
            state_hash=token_hash(state),
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )
    )
    await db.commit()
    return {
        "authorization_url": "https://intervals.icu/oauth/authorize?"
        + urlencode(
            {
                "client_id": settings.INTERVALS_CLIENT_ID,
                "redirect_uri": settings.INTERVALS_REDIRECT_URI,
                "scope": ",".join(SCOPES),
                "state": state,
            }
        ),
        "scopes": SCOPES,
    }


@router.post("/connections/intervals/callback")
async def callback(
    payload: Callback,
    user: User = Depends(current_user),
    session: AuthSession = Depends(current_session),
    db: AsyncSession = Depends(get_db),
):
    configured()
    # Conditional UPDATE claims a state exactly once, including concurrent callbacks.
    state = await db.scalar(
        select(ProviderOAuthState).where(ProviderOAuthState.state_hash == token_hash(payload.state))
    )
    if not state or state.user_id != user.id or state.session_id != session.id:
        raise HTTPException(400, "INTERVALS_INVALID_STATE")
    await own_athlete(db, user, state.athlete_id)
    claimed = await db.execute(
        update(ProviderOAuthState)
        .where(
            ProviderOAuthState.id == state.id,
            ProviderOAuthState.consumed_at.is_(None),
            ProviderOAuthState.expires_at > datetime.now(UTC),
        )
        .values(consumed_at=datetime.now(UTC))
        .execution_options(synchronize_session=False)
    )
    if claimed.rowcount != 1:
        raise HTTPException(400, "INTERVALS_STATE_EXPIRED_OR_USED")
    await db.commit()  # Never retry a consumed code if provider exchange failed.
    if payload.error or not payload.code:
        raise HTTPException(400, "INTERVALS_AUTHORIZATION_DENIED")
    try:
        token = await RealIntervalsAdapter().exchange_code(payload.code)
    except IntervalsError as exc:
        raise HTTPException(exc.status, exc.code) from None
    # Consent/assignment can change while exchanging credentials.
    await own_athlete(db, user, state.athlete_id)
    connection = await db.scalar(
        select(AthleteConnection)
        .where(AthleteConnection.athlete_id == state.athlete_id, AthleteConnection.provider == PROVIDER)
        .with_for_update()
    )
    external = str(token["athlete"]["id"])
    duplicate = await db.scalar(
        select(AthleteConnection.id).where(
            AthleteConnection.provider == PROVIDER,
            AthleteConnection.external_athlete_id == external,
            AthleteConnection.athlete_id != state.athlete_id,
            AthleteConnection.status.in_(["connected", "syncing"]),
        )
    )
    if duplicate:
        await RealIntervalsAdapter().disconnect(token["access_token"])
        raise HTTPException(409, "INTERVALS_ATHLETE_ALREADY_CONNECTED")
    if connection is None:
        connection = AthleteConnection(athlete_id=state.athlete_id, provider=PROVIDER, status="connected")
        db.add(connection)
    connection.external_athlete_id = external
    connection.access_token_enc = cipher().encrypt(token["access_token"].encode()).decode()
    connection.refresh_token_enc = None
    connection.scopes = str(token["scope"]).split(",")
    connection.status = "connected"
    await enqueue_sync(db, state.athlete_id, backfill=True, key=f"intervals:backfill:state:{state.id}")
    add_audit(db, actor_id=user.id, entity="athlete_connection", entity_id=state.athlete_id, action="authorize")
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        await RealIntervalsAdapter().disconnect(token["access_token"])
        raise HTTPException(409, "INTERVALS_ATHLETE_ALREADY_CONNECTED") from None
    return {"status": "connected", "sync": "queued", "backfill_days": settings.INTERVALS_BACKFILL_DAYS}


@router.get("/connections/intervals/{athlete_id}")
async def connection_status(athlete_id: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await require_athlete_access(db, user, athlete_id)
    connection = await db.scalar(
        select(AthleteConnection).where(
            AthleteConnection.athlete_id == athlete_id, AthleteConnection.provider == PROVIDER
        )
    )
    jobs = (await db.scalars(select(Job).where(Job.kind == "intervals_sync").order_by(Job.id.desc()).limit(100))).all()
    own_jobs = [j for j in jobs if j.payload.get("athlete_id") == athlete_id]
    return {
        "provider": PROVIDER,
        "status": connection.status if connection else "not_connected",
        "last_sync_at": connection.last_sync_at if connection else None,
        "scopes": connection.scopes if connection else [],
        "sync_status": own_jobs[0].status if own_jobs else None,
        "manual_fit_available": True,
    }


@router.post("/connections/intervals/{athlete_id}/sync", status_code=202)
async def sync(athlete_id: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await own_athlete(db, user, athlete_id)
    connection = await db.scalar(
        select(AthleteConnection).where(
            AthleteConnection.athlete_id == athlete_id, AthleteConnection.provider == PROVIDER
        )
    )
    if not connection or connection.status not in {"connected", "syncing"}:
        raise HTTPException(409, "INTERVALS_RECONNECT_REQUIRED")
    # One user-triggered sync per minute; retries share durable job identity.
    key = f"intervals:manual:{athlete_id}:{datetime.now(UTC).strftime('%Y%m%d%H%M')}"
    job_id = await enqueue_sync(db, athlete_id, key=key)
    await db.commit()
    return {"job_id": job_id, "status": "queued"}


@router.delete("/connections/intervals/{athlete_id}")
async def disconnect(athlete_id: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await own_athlete(db, user, athlete_id)
    connection = await db.scalar(
        select(AthleteConnection)
        .where(AthleteConnection.athlete_id == athlete_id, AthleteConnection.provider == PROVIDER)
        .with_for_update()
    )
    if not connection:
        return {"status": "revoked"}
    # Keep encrypted token for retry if remote revocation fails; ingestion stops immediately.
    connection.status = "disconnect_pending"
    await db.commit()
    if connection.access_token_enc:
        try:
            await RealIntervalsAdapter().disconnect(cipher().decrypt(connection.access_token_enc.encode()).decode())
        except IntervalsError as exc:
            await queue_remote_disconnect(db, connection)
            await db.commit()
            raise HTTPException(exc.status, "INTERVALS_REMOTE_DISCONNECT_PENDING") from None
    connection.status = "revoked"
    connection.access_token_enc = connection.refresh_token_enc = None
    jobs = (
        await db.scalars(select(Job).where(Job.kind == "intervals_sync", Job.status.in_(["pending", "running"])))
    ).all()
    for job in jobs:
        if job.payload.get("athlete_id") == athlete_id:
            job.status = "cancelled"
    add_audit(db, actor_id=user.id, entity="athlete_connection", entity_id=athlete_id, action="disconnect")
    await db.commit()
    return {"status": "revoked", "manual_fit_available": True}


@router.post("/connections/intervals/webhook")
async def webhook(request: Request, db: AsyncSession = Depends(get_db)):
    if not settings.INTERVALS_WEBHOOK_SECRET:
        raise HTTPException(503, "INTERVALS_WEBHOOK_CONFIGURATION_REQUIRED")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 1024 * 1024:
            raise HTTPException(413, "Webhook demasiado grande")
    try:
        payload = json.loads(body)
    except ValueError:
        raise HTTPException(400, "INTERVALS_INVALID_WEBHOOK") from None
    if (
        not isinstance(payload, dict)
        or not isinstance(payload.get("secret"), str)
        or not secrets.compare_digest(payload["secret"].encode(), settings.INTERVALS_WEBHOOK_SECRET.encode())
    ):
        raise HTTPException(401, "INTERVALS_WEBHOOK_UNAUTHORIZED")
    events = payload.get("events")
    if not isinstance(events, list) or len(events) > 100:
        raise HTTPException(422, "INTERVALS_INVALID_WEBHOOK_EVENTS")
    received = 0
    allowed = {
        "ACTIVITY_UPLOADED",
        "ACTIVITY_ANALYZED",
        "ACTIVITY_UPDATED",
        "ACTIVITY_DELETED",
        "WELLNESS_UPDATED",
        "CALENDAR_UPDATED",
        "SPORT_SETTINGS_UPDATED",
        "ATHLETE_UPDATED",
    }
    for event in events:
        if not isinstance(event, dict) or event.get("type") not in allowed:
            continue
        if not isinstance(event.get("athlete_id"), (str, int)) or not isinstance(event.get("timestamp"), str):
            raise HTTPException(422, "INTERVALS_INVALID_WEBHOOK_EVENT")
        if event["type"].startswith("ACTIVITY_") and not isinstance(event.get("activity"), dict):
            raise HTTPException(422, "INTERVALS_INVALID_WEBHOOK_ACTIVITY")
        try:
            timestamp = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                raise ValueError()
            external_id(event["athlete_id"])
            if event["type"].startswith("ACTIVITY_"):
                external_id(event["activity"].get("id", ""))
        except (ValueError, IntervalsError):
            raise HTTPException(422, "INTERVALS_INVALID_WEBHOOK_EVENT") from None
        connection = await db.scalar(
            select(AthleteConnection).where(
                AthleteConnection.provider == PROVIDER,
                AthleteConnection.external_athlete_id == str(event["athlete_id"]),
                AthleteConnection.status.in_(["connected", "syncing"]),
            )
        )
        if not connection:
            continue
        try:
            await require_provider_consent(db, connection.athlete_id, "training_data_processing")
        except HTTPException:
            continue
        key = f"intervals:event:{connection.athlete_id}:{digest(event)}"
        if await db.scalar(
            select(IngestionEvent.id).where(IngestionEvent.provider == PROVIDER, IngestionEvent.external_id == key)
        ):
            continue
        try:
            async with db.begin_nested():
                db.add(
                    IngestionEvent(
                        athlete_id=connection.athlete_id,
                        provider=PROVIDER,
                        external_id=key,
                        payload_hash=digest(event),
                        status="received",
                    )
                )
                await enqueue_sync(db, connection.athlete_id, event=event, key=key)
                await db.flush()
            received += 1
        except IntegrityError:
            pass  # Concurrent delivery already enqueued same exact event.
    await db.commit()
    return {"accepted": received}
