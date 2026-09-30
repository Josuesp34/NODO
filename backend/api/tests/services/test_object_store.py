import asyncio
import os
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
import httpx

from app.services import object_store
from app.services.object_store import (
    ObjectStoreError,
    delete_athlete_files,
    prune_expired_files,
    put_file,
    read_file,
    valid_key,
)


def test_local_store_isolates_owners_and_retains_recent_files(tmp_path, monkeypatch):
    monkeypatch.setattr(
        object_store,
        "settings",
        SimpleNamespace(
            STORAGE_BACKEND="local",
            STORAGE_LOCAL_PATH=str(tmp_path),
            ENVIRONMENT="development",
            MAX_FIT_BYTES=1024,
        ),
    )

    async def scenario():
        old_key = "fit/1/" + "a" * 64 + ".fit"
        other_key = "fit/2/" + "b" * 64 + ".fit"
        await put_file(old_key, b"synthetic-old")
        await put_file(other_key, b"synthetic-other")
        old = datetime.now(UTC) - timedelta(days=10)
        os.utime(tmp_path / old_key, (old.timestamp(), old.timestamp()))
        assert await prune_expired_files(datetime.now(UTC) - timedelta(days=5)) == 1
        assert await read_file(other_key) == b"synthetic-other"
        assert await delete_athlete_files(1) == 0
        assert await delete_athlete_files(2) == 1
        with pytest.raises(ObjectStoreError):
            await read_file(other_key)

    asyncio.run(scenario())


def test_object_keys_reject_traversal_and_arbitrary_paths():
    for key in ("fit/1/../../secret", "fit/0/" + "a" * 64 + ".fit", "other/1/a.fit", "fit/1/not-a-hash.fit"):
        with pytest.raises(ObjectStoreError):
            valid_key(key)


def test_gcs_contract_deletes_each_generation_only_in_owner_prefix(monkeypatch):
    monkeypatch.setattr(object_store, "settings", SimpleNamespace(STORAGE_BACKEND="gcs", STORAGE_BUCKET="synthetic-bucket", ENVIRONMENT="production"))
    calls = []
    key = "fit/1/" + "a" * 64 + ".fit"

    def transport(request):
        calls.append(request)
        assert request.url.host == "storage.googleapis.com"
        assert request.headers["Authorization"] == "Bearer synthetic-token"
        if request.method == "DELETE":
            assert request.url.params["generation"] in {"1", "2"}
            assert request.url.path.endswith(key)
            return httpx.Response(204)
        assert request.url.params["prefix"] in {"fit/1/", "export/1/"}
        assert request.url.params["versions"] == "true"
        if request.url.params["prefix"] == "export/1/":
            return httpx.Response(200, json={"items": []})
        page = request.url.params.get("pageToken")
        data = {"items": [{"name": key, "generation": "2" if page else "1", "updated": "2026-09-01T00:00:00Z"}]}
        if not page:
            data["nextPageToken"] = "second"
        return httpx.Response(200, json=data)

    original = httpx.AsyncClient
    monkeypatch.setattr(object_store.httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(transport), **kwargs))

    async def authorization():
        return {"Authorization": "Bearer synthetic-token"}

    monkeypatch.setattr(object_store, "authorization", authorization)
    assert asyncio.run(delete_athlete_files(1)) == 2
    assert len([request for request in calls if request.method == "DELETE"]) == 2


def test_production_cleanup_fails_closed_without_configured_storage(monkeypatch):
    monkeypatch.setattr(object_store, "settings", SimpleNamespace(STORAGE_BACKEND="none", ENVIRONMENT="production"))
    with pytest.raises(ObjectStoreError):
        asyncio.run(delete_athlete_files(1))
