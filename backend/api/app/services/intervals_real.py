"""Official contracts: forum.intervals.icu/t/2759, /t/80090 and /api/v1/docs.
No refresh token, HMAC or undocumented OAuth grant parameters are invented.
"""

import asyncio
import hashlib
import json
import math
import re
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.infrastructure.database.models import Activity, User
from app.infrastructure.database.models.product import AthleteConnection, IngestionEvent, Job, Observation
from app.infrastructure.database.models.providers import ProviderRecord
from app.services.provider_policy import require_provider_consent

PROVIDER = "intervals_icu"
BASE = "https://intervals.icu"
SCOPES = ("ACTIVITY:READ", "WELLNESS:READ", "CALENDAR:READ")
SOURCES = {
    "UPLOAD",
    "MANUAL",
    "GARMIN_CONNECT",
    "OAUTH_CLIENT",
    "DROPBOX",
    "POLAR",
    "SUUNTO",
    "COROS",
    "WAHOO",
    "ZWIFT",
    "ZEPP",
    "CONCEPT2",
    "HUAWEI",
}


class IntervalsError(Exception):
    def __init__(self, code: str, status: int = 502):
        self.code, self.status = code, status
        # Ephemeral only: callback encrypts this capability into durable cleanup.
        # It never appears in exception text or a public response.
        self.cleanup_token: str | None = None
        super().__init__(code)


def cipher() -> Fernet:
    try:
        return Fernet(settings.PROVIDER_TOKEN_ENCRYPTION_KEY.encode())
    except (ValueError, TypeError):
        raise HTTPException(503, "INTERVALS_ENCRYPTION_CONFIGURATION_REQUIRED") from None


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def external_id(value) -> str:
    value = str(value)
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", value):
        raise IntervalsError("INTERVALS_INVALID_EXTERNAL_ID")
    return value


class RealIntervalsAdapter:
    def __init__(self, transport=None):
        self.transport = transport

    async def request(self, method, path, token=None, **kwargs):
        # Fixed origin and no redirects prevent credential forwarding/SSRF.
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        for attempt in range(3):
            # Worker executes jobs sequentially: pace REST calls below the documented ~9/s envelope.
            await asyncio.sleep(0.15)
            try:
                async with httpx.AsyncClient(
                    transport=self.transport, timeout=settings.INTERVALS_TIMEOUT_SECONDS, follow_redirects=False
                ) as client:
                    async with client.stream(method, BASE + path, headers=headers, **kwargs) as response:
                        if response.status_code in {401, 403}:
                            raise IntervalsError("INTERVALS_RECONNECT_REQUIRED", 409)
                        if response.status_code in {429, 500, 502, 503, 504}:
                            if method == "GET" and attempt < 2:
                                await asyncio.sleep(0.2 * (attempt + 1))
                                continue
                            raise IntervalsError("INTERVALS_TEMPORARILY_UNAVAILABLE", 503)
                        if not 200 <= response.status_code < 300:
                            raise IntervalsError("INTERVALS_REQUEST_REJECTED")
                        data = bytearray()
                        async for chunk in response.aiter_bytes():
                            data.extend(chunk)
                            if len(data) > 8 * 1024 * 1024:
                                raise IntervalsError("INTERVALS_RESPONSE_TOO_LARGE")
                        if not data:
                            return None
                        try:
                            return json.loads(data)
                        except ValueError:
                            raise IntervalsError("INTERVALS_INVALID_RESPONSE") from None
            except (httpx.TimeoutException, httpx.NetworkError):
                if method == "GET" and attempt < 2:
                    await asyncio.sleep(0.2 * (attempt + 1))
                    continue
                raise IntervalsError("INTERVALS_TEMPORARILY_UNAVAILABLE", 503) from None

    async def exchange_code(self, code):
        result = await self.request(
            "POST",
            "/api/oauth/token",
            data={
                "client_id": settings.INTERVALS_CLIENT_ID,
                "client_secret": settings.INTERVALS_CLIENT_SECRET,
                "code": code,
            },
        )
        issued = result.get("access_token") if isinstance(result, dict) else None
        issued = issued if isinstance(issued, str) and issued else None
        try:
            if not isinstance(result, dict) or str(result.get("token_type", "")).lower() != "bearer" or not issued:
                raise IntervalsError("INTERVALS_INVALID_TOKEN_RESPONSE")
            athlete = result.get("athlete")
            if not isinstance(athlete, dict) or not athlete.get("id"):
                raise IntervalsError("INTERVALS_INVALID_TOKEN_RESPONSE")
            external_id(athlete["id"])
            granted = str(result.get("scope", "")).split(",")
            if not set(SCOPES).issubset(granted):
                raise IntervalsError("INTERVALS_REQUIRED_SCOPES_MISSING", 422)
        except IntervalsError as exc:
            if issued:
                try:
                    await self.disconnect(issued)
                except IntervalsError:
                    exc.cleanup_token = issued
            raise
        return result

    async def disconnect(self, token):
        try:
            await self.request("DELETE", "/api/v1/disconnect-app", token)
        except IntervalsError as exc:
            if exc.code != "INTERVALS_RECONNECT_REQUIRED":
                raise

    async def activity(self, token, activity_id):
        return await self.request(
            "GET", f"/api/v1/activity/{external_id(activity_id)}", token, params={"intervals": "true"}
        )

    async def window(self, token, athlete_id, start, end):
        path = f"/api/v1/athlete/{external_id(athlete_id)}"
        params = {"oldest": start.isoformat(), "newest": end.isoformat()}
        result = {}
        for kind, suffix in (("activity", "/activities"), ("wellness", "/wellness"), ("calendar", "/events")):
            rows = await self.request("GET", path + suffix, token, params=params)
            if not isinstance(rows, list) or len(rows) > 5000:
                raise IntervalsError("INTERVALS_INVALID_COLLECTION")
            result[kind] = rows
        return result


def number(value, minimum=0):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < minimum:
        return None
    return value


async def store_record(db, athlete_id, kind, payload):
    identifier = external_id(payload.get("id", ""))
    record = await db.scalar(
        select(ProviderRecord).where(
            ProviderRecord.athlete_id == athlete_id,
            ProviderRecord.provider == PROVIDER,
            ProviderRecord.kind == kind,
            ProviderRecord.external_id == identifier,
        )
    )
    if record is None:
        db.add(
            ProviderRecord(athlete_id=athlete_id, provider=PROVIDER, kind=kind, external_id=identifier, payload=payload)
        )
    else:
        record.payload = payload


async def ingest_activity(db, athlete: User, payload: dict):
    # Strava stubs have no usable source; device_name alone never proves origin.
    if payload.get("source") not in SOURCES or payload.get("strava_id"):
        return False
    identifier = external_id(payload.get("id", ""))
    try:
        start = datetime.fromisoformat(payload["start_date"].replace("Z", "+00:00"))
        if start.tzinfo is None:
            raise ValueError()
        timezone = payload.get("timezone") or athlete.timezone
        ZoneInfo(timezone)
    except (KeyError, ValueError, TypeError):
        raise IntervalsError("INTERVALS_INVALID_ACTIVITY_TIME") from None
    activity = await db.scalar(
        select(Activity).where(Activity.provider == PROVIDER, Activity.external_id == f"{athlete.id}:{identifier}")
    )
    if activity is None:
        activity = Activity(
            athlete_id=athlete.id,
            provider=PROVIDER,
            external_id=f"{athlete.id}:{identifier}",
            file_name=f"intervals-{identifier}",
            file_hash=digest([PROVIDER, athlete.id, identifier]),
        )
        db.add(activity)
    activity.start_time = start
    activity.timezone = timezone
    activity.sport_type = {"Run": "running", "Ride": "cycling", "Swim": "swimming"}.get(payload.get("type"), "other")
    activity.total_duration_sec = number(payload.get("moving_time")) or number(payload.get("elapsed_time")) or 0
    activity.total_distance_m = number(payload.get("distance")) or 0
    activity.avg_heart_rate = number(payload.get("average_heartrate"), 1)
    activity.max_heart_rate = number(payload.get("max_heartrate"), 1)
    activity.avg_speed_mps = number(payload.get("average_speed"))
    activity.total_elevation_gain_m = number(payload.get("total_elevation_gain"))
    # Provider load is preserved as provider evidence; never labelled calculated NODO TRIMP/TSS.
    await store_record(db, athlete.id, "activity", payload)
    await db.flush()
    return True


async def ingest_wellness(db, athlete: User, payload: dict):
    try:
        local_day = date.fromisoformat(payload["id"])
        start = datetime.combine(local_day, datetime.min.time(), ZoneInfo(athlete.timezone))
    except (KeyError, ValueError, TypeError):
        raise IntervalsError("INTERVALS_INVALID_WELLNESS_DATE") from None
    # Unspecified hrv/vo2max method is explicit, never promoted to laboratory measurement.
    fields = {
        "hrv": ("hrv", "ms", "provider_unspecified"),
        "hrvSDNN": ("hrv", "ms", "SDNN"),
        "sleepSecs": ("sleep", "seconds", "provider_unspecified"),
        "restingHR": ("resting_hr", "bpm", "provider_unspecified"),
        "vo2max": ("vo2max", "ml/kg/min", "provider_estimate"),
        "weight": ("weight", "kg", "provider_unspecified"),
    }
    # Replacing a daily provider record removes metrics cleared upstream, preserving manual observations.
    await db.execute(
        delete(Observation).where(
            Observation.athlete_id == athlete.id,
            Observation.source == PROVIDER,
            Observation.external_id.like(f"wellness:{local_day}:%"),
        )
    )
    for field, (metric, unit, method) in fields.items():
        value = number(payload.get(field))
        if value is None:
            continue
        db.add(
            Observation(
                athlete_id=athlete.id,
                metric_type=metric,
                value=value,
                unit=unit,
                method=method,
                source=PROVIDER,
                external_id=f"wellness:{local_day}:{field}",
                observed_start=start,
                observed_end=datetime.combine(
                    local_day + timedelta(days=1), datetime.min.time(), ZoneInfo(athlete.timezone)
                ),
                received_at=datetime.now(UTC),
                timezone=athlete.timezone,
                quality="partial",
            )
        )
    await store_record(db, athlete.id, "wellness", payload)


async def enqueue_sync(db, athlete_id, *, backfill=False, event=None, key=None):
    now = datetime.now(UTC)
    key = key or f"intervals:sync:{athlete_id}:{now.isoformat()}"
    existing = await db.scalar(select(Job.id).where(Job.dedupe_key == key))
    if existing:
        return existing
    job = Job(
        kind="intervals_sync",
        payload={"athlete_id": athlete_id, "backfill": backfill, "event": event},
        run_after=now,
        dedupe_key=key,
        max_attempts=settings.JOB_MAX_ATTEMPTS,
    )
    db.add(job)
    await db.flush()
    return job.id


async def queue_token_disconnect(db, token_enc: str | None):
    """Cleanup is independent of a person/connection that may already be erased."""
    if not token_enc:
        return None
    key = f"intervals:disconnect:{digest(token_enc)}"
    existing = await db.scalar(select(Job.id).where(Job.dedupe_key == key))
    if existing:
        return existing
    job = Job(
        kind="intervals_disconnect",
        payload={"token_enc": token_enc},
        run_after=datetime.now(UTC),
        dedupe_key=key,
        max_attempts=settings.JOB_MAX_ATTEMPTS,
    )
    try:
        async with db.begin_nested():
            db.add(job)
            await db.flush()
    except IntegrityError:
        existing = await db.scalar(select(Job.id).where(Job.dedupe_key == key))
        if existing is None:
            raise
        return existing
    return job.id


async def queue_remote_disconnect(db, connection):
    return await queue_token_disconnect(db, connection.access_token_enc)


async def execute_intervals_disconnect_job(db, job):
    token_enc = job.payload.get("token_enc")
    if token_enc:
        await RealIntervalsAdapter().disconnect(cipher().decrypt(token_enc.encode()).decode())
    await db.execute(
        update(AthleteConnection)
        .where(AthleteConnection.access_token_enc == token_enc, AthleteConnection.status == "disconnect_pending")
        .values(status="revoked", access_token_enc=None, refresh_token_enc=None)
    )
    job.payload = {"revoked": True}


async def execute_intervals_job(db, job):
    athlete_id, job_id, job_key = int(job.payload["athlete_id"]), job.id, job.dedupe_key
    event, backfill = job.payload.get("event"), job.payload.get("backfill")
    athlete = await db.get(User, athlete_id)
    if athlete is None or athlete.deleted_at is not None:
        return
    await require_provider_consent(db, athlete_id, "training_data_processing")
    connection = await db.scalar(
        select(AthleteConnection).where(
            AthleteConnection.athlete_id == athlete_id, AthleteConnection.provider == PROVIDER
        )
    )
    if not connection or connection.status not in {"connected", "syncing"} or not connection.access_token_enc:
        return
    token_enc, remote_id = connection.access_token_enc, connection.external_athlete_id
    token = cipher().decrypt(token_enc.encode()).decode()
    adapter = RealIntervalsAdapter()
    await db.commit()  # Never hold database locks while contacting a provider.

    async def still_authorized():
        await db.refresh(athlete)
        if athlete.deleted_at is not None:
            return False
        try:
            await require_provider_consent(db, athlete_id, "training_data_processing")
        except HTTPException:
            return False
        await db.refresh(connection, with_for_update=True)
        return connection.status in {"connected", "syncing"} and connection.access_token_enc == token_enc

    imported, ignored = 0, 0
    try:
        if event and event["type"] == "ACTIVITY_DELETED":
            if not await still_authorized():
                return
            identifier = external_id(event["activity"]["id"])
            await db.execute(
                delete(Activity).where(
                    Activity.athlete_id == athlete_id,
                    Activity.provider == PROVIDER,
                    Activity.external_id == f"{athlete_id}:{identifier}",
                )
            )
            await db.execute(
                delete(ProviderRecord).where(
                    ProviderRecord.athlete_id == athlete_id,
                    ProviderRecord.provider == PROVIDER,
                    ProviderRecord.kind == "activity",
                    ProviderRecord.external_id == identifier,
                )
            )
        elif event and event["type"] == "CALENDAR_UPDATED":
            if not await still_authorized():
                return
            for payload in event.get("events", []):
                await store_record(db, athlete_id, "calendar", payload)
            for payload in event.get("deleted_events", []):
                identifier = external_id(payload["id"] if isinstance(payload, dict) else payload)
                await db.execute(
                    delete(ProviderRecord).where(
                        ProviderRecord.athlete_id == athlete_id,
                        ProviderRecord.provider == PROVIDER,
                        ProviderRecord.kind == "calendar",
                        ProviderRecord.external_id == identifier,
                    )
                )
        elif event and event["type"].startswith("ACTIVITY_"):
            payload = await adapter.activity(token, event["activity"]["id"])
            if not await still_authorized():
                return
            imported += int(await ingest_activity(db, athlete, payload))
        else:
            today = datetime.now(ZoneInfo(athlete.timezone)).date()
            oldest = today - timedelta(days=settings.INTERVALS_BACKFILL_DAYS if backfill else 7)
            cursor = oldest
            while cursor <= today:
                end = min(cursor + timedelta(days=6), today)
                records = await adapter.window(token, remote_id, cursor, end)
                details = []
                for payload in records["activity"]:
                    if payload.get("source") in SOURCES and not payload.get("strava_id"):
                        details.append(await adapter.activity(token, payload["id"]))
                    else:
                        ignored += 1
                if not await still_authorized():
                    return
                connection.status = "syncing"
                for payload in details:
                    imported += int(await ingest_activity(db, athlete, payload))
                for payload in records["wellness"]:
                    await ingest_wellness(db, athlete, payload)
                # External calendar is evidence only; NODO publication remains separate.
                for payload in records["calendar"]:
                    await store_record(db, athlete_id, "calendar", payload)
                await db.commit()  # Each complete window is atomic/idempotent; revoked users stop before next write.
                cursor = end + timedelta(days=1)
            await store_record(
                db,
                athlete_id,
                "sync_status",
                {
                    "id": "latest",
                    "start": str(oldest),
                    "end": str(today),
                    "imported_activities": imported,
                    "ignored_unsupported_source": ignored,
                    "note": "Strava/unknown origins excluded. Provider intervals remain evidence, not FIT laps.",
                },
            )
        if not await still_authorized():
            return
        connection.status = "connected"
        connection.last_sync_at = datetime.now(UTC)
        if not event:
            key = f"intervals:scheduled:{job_id}"
            if not await db.scalar(select(Job.id).where(Job.dedupe_key == key)):
                db.add(
                    Job(
                        kind="intervals_sync",
                        payload={"athlete_id": athlete_id, "backfill": False},
                        run_after=datetime.now(UTC) + timedelta(hours=settings.INTERVALS_SYNC_INTERVAL_HOURS),
                        dedupe_key=key,
                        max_attempts=settings.JOB_MAX_ATTEMPTS,
                    )
                )
    except IntervalsError as exc:
        if exc.code == "INTERVALS_RECONNECT_REQUIRED":
            await db.refresh(connection, with_for_update=True)
            if connection.access_token_enc == token_enc:
                connection.status = "reconnect_required"
                connection.access_token_enc = None
                connection.refresh_token_enc = None
            return
        raise
    if event:
        ingestion = await db.scalar(
            select(IngestionEvent).where(IngestionEvent.provider == PROVIDER, IngestionEvent.external_id == job_key)
        )
        if ingestion:
            ingestion.status = "processed"
