"""Synthetic HTTP journeys exercise authorization before reading private FIT bytes."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select, text
from test_pilot_product import make_fit
from test_privacy_notifications import private_api as _private_api

from app.api import activity_routes, file_routes
from app.infrastructure.database.models import Activity
from app.infrastructure.database.models.product import Job
from app.services import object_store, privacy_jobs


@pytest.fixture(params=["sqlite", "postgres"])
def files_api(request, monkeypatch, tmp_path):
    # Reuse the isolated consent/FK-aware fixture, never a real athlete database.
    for api in _private_api.__wrapped__(request, monkeypatch):
        if request.param == "postgres":
            # create_all declares the partitioned parent; Alembic normally creates
            # its default partition. Reproduce that fixture-only invariant here.
            async def create_partition(sessions=api.sessions):
                async with sessions() as db:
                    await db.execute(
                        text("CREATE TABLE telemetry_records_default PARTITION OF telemetry_records DEFAULT")
                    )
                    await db.commit()

            asyncio.run(create_partition())
        api.config.STORAGE_BACKEND = "local"
        api.config.STORAGE_LOCAL_PATH = str(tmp_path)
        api.config.MAX_FIT_BYTES = 1024 * 1024
        monkeypatch.setattr(object_store, "settings", api.config)
        monkeypatch.setattr(activity_routes, "settings", api.config)
        api.client.app.include_router(activity_routes.router, prefix="/api/v1")
        api.client.app.include_router(file_routes.router, prefix="/api/v1")
        api.storage_root = tmp_path
        yield api


def upload(api, identity_index=1):
    athlete_id, headers = api.identities[identity_index]
    content = make_fit()
    response = api.client.post(
        f"/api/v1/athletes/{athlete_id}/activities/fit",
        headers=headers,
        files={"file": ("synthetic.fit", content)},
    )
    assert response.status_code == 201, response.text
    activity = response.json()
    return activity, content, f"/api/v1/athletes/{athlete_id}/activities/{activity['activity_id']}/file"


def in_database(api, operation):
    async def run():
        async with api.sessions() as db:
            return await operation(db)

    return asyncio.run(run())


def test_download_scopes_athlete_activity_and_provider_before_storage(files_api, monkeypatch):
    api = files_api
    activity, content, path = upload(api)
    athlete_id, own = api.identities[1]
    other_id, other = api.identities[2]
    coach = api.identities[0][1]
    read = AsyncMock(wraps=object_store.read_file)
    monkeypatch.setattr(file_routes, "read_file", read)

    assert api.client.get(path).status_code == 401
    assert api.client.get(path, headers=other).status_code == 404
    mismatched = f"/api/v1/athletes/{other_id}/activities/{activity['activity_id']}/file"
    assert api.client.get(mismatched, headers=other).status_code == 404
    read.assert_not_awaited()

    for headers in (own, coach):
        response = api.client.get(path, headers=headers)
        assert response.status_code == 200
        assert response.content == content
        assert response.headers["cache-control"] == "private, no-store"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["content-disposition"] == 'attachment; filename="actividad.fit"'
    assert {call.args[0] for call in read.await_args_list} == {f"fit/{athlete_id}/{activity['file_hash']}.fit"}

    async def external_source(db):
        row = await db.get(Activity, activity["activity_id"])
        row.provider = "intervals.icu"
        await db.commit()

    in_database(api, external_source)
    read.reset_mock()
    assert api.client.get(path, headers=own).status_code == 404
    read.assert_not_awaited()


def test_consent_withdrawal_blocks_download_and_upload_without_storage_effect(files_api, monkeypatch):
    api = files_api
    _, _, path = upload(api)
    athlete_id, own = api.identities[1]
    consent = api.client.post(
        "/api/v1/consents", headers=own, json={"scope": "training_data_processing", "version": "pilot-v1"}
    )
    assert consent.status_code == 201
    assert api.client.delete(f"/api/v1/consents/{consent.json()['id']}", headers=own).status_code == 204
    read, put = AsyncMock(), AsyncMock()
    monkeypatch.setattr(file_routes, "read_file", read)
    monkeypatch.setattr(object_store, "put_file", put)
    for headers in (own, api.identities[0][1]):
        assert api.client.get(path, headers=headers).status_code == 403
        assert (
            api.client.post(
                f"/api/v1/athletes/{athlete_id}/activities/fit",
                headers=headers,
                files={"file": ("synthetic.fit", make_fit())},
            ).status_code
            == 403
        )
    read.assert_not_awaited()
    put.assert_not_awaited()


@pytest.mark.parametrize("content_length", [None, "1"])
def test_oversized_fit_is_rejected_without_storage_or_db_writes(files_api, monkeypatch, content_length):
    api = files_api
    api.config.MAX_FIT_BYTES = 1024
    athlete_id, headers = api.identities[1]
    put = AsyncMock()
    monkeypatch.setattr(object_store, "put_file", put)
    request = api.client.build_request(
        "POST",
        f"/api/v1/athletes/{athlete_id}/activities/fit",
        headers=headers,
        files={"file": ("synthetic.fit", b"x" * 1025)},
    )
    if content_length is None:
        del request.headers["content-length"]
    else:
        request.headers["content-length"] = content_length
    assert api.client.send(request).status_code == 413
    put.assert_not_awaited()

    async def count(db):
        assert await db.scalar(select(func.count()).select_from(Activity)) == 0
        assert await db.scalar(select(func.count()).select_from(Job)) == 0

    in_database(api, count)
    assert not list(api.storage_root.rglob("*.fit"))


def test_upload_cross_owner_denied_and_missing_storage_does_not_disclose_details(files_api, monkeypatch):
    api = files_api
    athlete_id, _ = api.identities[1]
    put = AsyncMock()
    monkeypatch.setattr(object_store, "put_file", put)
    denied = api.client.post(
        f"/api/v1/athletes/{athlete_id}/activities/fit",
        headers=api.identities[2][1],
        files={"file": ("synthetic.fit", b"unparsed-invalid-fit")},
    )
    assert denied.status_code == 404
    put.assert_not_awaited()
    put.side_effect = object_store.ObjectStoreError("secret-provider-path")
    failed = api.client.post(
        f"/api/v1/athletes/{athlete_id}/activities/fit",
        headers=api.identities[1][1],
        files={"file": ("synthetic.fit", make_fit())},
    )
    assert failed.status_code == 503
    assert "secret-provider-path" not in failed.text

    async def count(db):
        assert await db.scalar(select(func.count()).select_from(Activity)) == 0
        assert await db.scalar(select(func.count()).select_from(Job)) == 0

    in_database(api, count)


def test_account_erasure_queues_physical_cleanup_and_preserves_other_owner(files_api):
    api = files_api
    activity, _, path = upload(api)
    other_activity, other_content, other_path = upload(api, 2)
    athlete_id, own = api.identities[1]
    erased = api.client.request(
        "DELETE",
        "/api/v1/account",
        headers=own,
        json={"password": "Synthetic-test-password", "confirmation": "ELIMINAR MI CUENTA"},
    )
    assert erased.status_code == 204, erased.text
    assert api.client.get(path, headers=own).status_code == 401
    assert api.client.get(path, headers=api.identities[0][1]).status_code == 404
    # HTTP acknowledgement queues physical cleanup; it does not claim immediate blob removal.
    assert (api.storage_root / f"fit/{athlete_id}/{activity['file_hash']}.fit").exists()

    async def cleanup(db):
        job = await db.scalar(select(Job).where(Job.dedupe_key == f"erase-user-files:{athlete_id}"))
        assert job is not None and job.kind == "privacy_delete_user_files"
        assert await privacy_jobs.dispatch_privacy_job(db, job)
        assert job.payload == {"deleted_files": 1}
        await db.commit()

    in_database(api, cleanup)
    assert not (api.storage_root / f"fit/{athlete_id}/{activity['file_hash']}.fit").exists()
    response = api.client.get(other_path, headers=api.identities[2][1])
    assert response.status_code == 200 and response.content == other_content
    assert other_activity["file_hash"] == activity["file_hash"]  # Identical content remains owner-scoped.


def test_retention_requires_admin_and_eventually_removes_only_expired_files(files_api):
    api = files_api
    old, _, old_path = upload(api)
    _, recent_content, recent_path = upload(api, 2)
    athlete_id, own = api.identities[1]
    cutoff = datetime.now(UTC) - timedelta(days=api.config.DATA_RETENTION_DAYS + 1)
    key = api.storage_root / f"fit/{athlete_id}/{old['file_hash']}.fit"
    os.utime(key, (cutoff.timestamp(), cutoff.timestamp()))

    async def make_expired(db):
        row = await db.get(Activity, old["activity_id"])
        row.start_time = cutoff
        await db.commit()

    in_database(api, make_expired)
    policy = api.client.get("/api/v1/account/retention", headers=own)
    assert policy.json()["data_days"] == api.config.DATA_RETENTION_DAYS
    assert api.client.post("/api/v1/admin/privacy/retention", headers=own).status_code == 403
    for _ in range(2):
        assert api.client.post("/api/v1/admin/privacy/retention", headers=api.identities[0][1]).status_code == 202

    async def cleanup(db):
        jobs = (await db.scalars(select(Job).where(Job.kind == "privacy_retention"))).all()
        assert len(jobs) == 1
        assert await privacy_jobs.dispatch_privacy_job(db, jobs[0])
        assert jobs[0].payload["deleted_counts"]["storage_files"] == 1
        await db.commit()

    in_database(api, cleanup)
    assert api.client.get(old_path, headers=own).status_code == 404
    assert not key.exists()
    response = api.client.get(recent_path, headers=api.identities[2][1])
    assert response.status_code == 200 and response.content == recent_content
