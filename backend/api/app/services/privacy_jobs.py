"""Handlers to register in the shared PostgreSQL worker (no in-memory queue)."""

import asyncio
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.infrastructure.database.models.privacy import PrivacyArtifact
from app.infrastructure.database.models.product import Job
from app.services.notifications import push_cipher, send_notification
from app.services.privacy import sweep_retention


async def register_artifact(db: AsyncSession, *, user_id: int, storage_kind: str, locator: str) -> PrivacyArtifact:
    if storage_kind not in {"local", "gcs"}:
        raise ValueError("Almacenamiento no soportado")
    row = PrivacyArtifact(
        user_id=user_id,
        storage_kind=storage_kind,
        locator_enc=push_cipher().encrypt(locator.encode()).decode(),
        status="active",
    )
    db.add(row)
    await db.flush()
    return row


def _delete_storage_object(kind: str, locator: str) -> None:
    if kind == "local":
        root_value = getattr(settings, "PRIVACY_STORAGE_ROOT", "")
        if not root_value:
            raise RuntimeError("Private storage root unavailable")
        root = Path(root_value).resolve()
        # Relative, resolved path must stay inside the configured private store.
        candidate = Path(locator)
        if candidate.is_absolute():
            raise RuntimeError("Invalid private storage locator")
        target = (root / candidate).resolve()
        if target == root or root not in target.parents:
            raise RuntimeError("Invalid private storage locator")
        target.unlink(missing_ok=True)
    elif kind == "gcs":
        bucket, separator, object_name = locator.partition("/")
        allowed = {item.strip() for item in getattr(settings, "PRIVACY_GCS_BUCKETS", "").split(",") if item.strip()}
        if bucket not in allowed or not separator or not object_name:
            raise RuntimeError("Invalid private storage locator")
        import google.auth
        from google.auth.transport.requests import AuthorizedSession

        credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/devstorage.read_write"])
        with AuthorizedSession(credentials) as session:
            _delete_gcs_generations(session, bucket, object_name)
    else:
        raise RuntimeError("Private storage adapter unavailable")


def _delete_gcs_generations(session, bucket: str, object_name: str) -> None:
    """Delete exact-name live/noncurrent generations, never prefix neighbours.

    GCS objects.list versions=true and objects.delete generation contracts:
    https://cloud.google.com/storage/docs/json_api/v1/objects/list
    https://cloud.google.com/storage/docs/json_api/v1/objects/delete
    """
    base = f"https://storage.googleapis.com/storage/v1/b/{quote(bucket, safe='')}/o"
    object_url = f"{base}/{quote(object_name, safe='')}"
    page, seen = None, set()
    while True:
        params = {"prefix": object_name, "versions": "true", "maxResults": "1000"}
        if page:
            params["pageToken"] = page
        response = session.get(base, params=params, timeout=15, allow_redirects=False)
        if response.status_code != 200:
            raise RuntimeError("Private file inventory failed")
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("items", []), list):
            raise RuntimeError("Invalid private file inventory")
        for item in payload.get("items", []):
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                raise RuntimeError("Invalid private file inventory")
            if item["name"] != object_name:
                continue
            generation = item.get("generation")
            if not isinstance(generation, str) or not re.fullmatch(r"[1-9][0-9]{0,19}", generation):
                raise RuntimeError("Invalid private file generation")
            deleted = session.delete(
                object_url, params={"generation": generation}, timeout=15, allow_redirects=False
            )
            if deleted.status_code not in {204, 404}:
                raise RuntimeError("Private file generation cleanup failed")
        page = payload.get("nextPageToken")
        if page is None or page == "":
            return
        if not isinstance(page, str) or len(page) > 4096 or page in seen:
            raise RuntimeError("Invalid private file pagination")
        seen.add(page)


async def delete_artifact(db: AsyncSession, job: Job, *, transport=None) -> None:
    row = await db.get(PrivacyArtifact, job.payload["artifact_id"])
    if row is None or row.status == "deleted":
        return
    if row.status != "delete_pending" or not row.locator_enc:
        raise RuntimeError("Private file is not scheduled for deletion")
    try:
        locator = push_cipher().decrypt(row.locator_enc.encode()).decode()
        await asyncio.to_thread(transport or _delete_storage_object, row.storage_kind, locator)
    except Exception:
        raise RuntimeError("Private file cleanup failed; retry required") from None
    # Remove both encrypted locator and owner relation after physical cleanup.
    await db.delete(row)


async def dispatch_privacy_job(db: AsyncSession, job: Job) -> bool:
    if job.kind == "send_web_push":
        await send_notification(db, job)
    elif job.kind == "privacy_delete_file":
        await delete_artifact(db, job)
    elif job.kind == "privacy_delete_user_files":
        try:
            from app.services.object_store import delete_athlete_files

            count = await delete_athlete_files(int(job.payload["user_id"]))
            job.payload = {"deleted_files": count}
        except Exception:
            raise RuntimeError("Private user files cleanup failed; retry required") from None
    elif job.kind == "privacy_retention":
        counts = await sweep_retention(db)
        cutoff = datetime.now(UTC) - timedelta(days=settings.DATA_RETENTION_DAYS)
        # This adapter is owned by root and is integrated together with this handler.
        try:
            from app.services.object_store import prune_expired_files

            counts["storage_files"] = await prune_expired_files(cutoff)
        except Exception:
            raise RuntimeError("Private storage retention failed; retry required") from None
        artifacts = (
            await db.scalars(
                select(PrivacyArtifact).where(PrivacyArtifact.created_at < cutoff, PrivacyArtifact.status == "active")
            )
        ).all()
        for row in artifacts:
            row.status = "delete_pending"
            key = f"erase-file:{row.id}"
            if await db.scalar(select(Job.id).where(Job.dedupe_key == key)) is None:
                db.add(
                    Job(
                        kind="privacy_delete_file",
                        payload={"artifact_id": row.id},
                        run_after=datetime.now(UTC),
                        max_attempts=settings.JOB_MAX_ATTEMPTS,
                        dedupe_key=key,
                    )
                )
        job.payload = {"deleted_counts": counts, "files_pending": len(artifacts)}
    else:
        return False
    return True


async def run_retention_job() -> None:
    from app.core.database import async_session_maker

    async with async_session_maker() as db:
        job = Job(kind="privacy_retention", payload={})
        await dispatch_privacy_job(db, job)
        await db.commit()
        print(json.dumps(job.payload))


if __name__ == "__main__":
    try:
        asyncio.run(run_retention_job())
    except Exception:
        raise SystemExit("Retention failed: check private job configuration.") from None
