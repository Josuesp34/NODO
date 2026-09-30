"""GCS cleanup uses mocked HTTP sessions and never contacts Google Cloud."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import google.auth
import pytest
from google.auth.transport.requests import AuthorizedSession

from app.services import privacy_jobs


def response(status, payload=None):
    return SimpleNamespace(status_code=status, json=lambda: payload)


def mock_storage(monkeypatch, pages, deletion_statuses=(204,)):
    session = MagicMock(spec=AuthorizedSession)
    session.__enter__.return_value = session
    session.get.side_effect = pages
    session.delete.side_effect = [response(status) for status in deletion_statuses]
    credentials = object()
    monkeypatch.setattr(google.auth, "default", lambda **kwargs: (credentials, "synthetic-nodo"))
    monkeypatch.setattr("google.auth.transport.requests.AuthorizedSession", lambda actual: session)
    monkeypatch.setattr(privacy_jobs, "settings", SimpleNamespace(PRIVACY_GCS_BUCKETS="synthetic-private"))
    return session


def test_registered_gcs_asset_deletes_all_pages_and_only_exact_generations(monkeypatch):
    name = "fit/1/" + "a" * 64 + ".fit"
    session = mock_storage(
        monkeypatch,
        [
            response(
                200,
                {
                    "items": [{"name": name, "generation": "1"}, {"name": name + ".neighbour", "generation": "3"}],
                    "nextPageToken": "synthetic-next-page",
                },
            ),
            response(200, {"items": [{"name": name, "generation": "2"}]}),
        ],
        (204, 404),
    )
    privacy_jobs._delete_storage_object("gcs", "synthetic-private/" + name)
    assert [call.kwargs["params"]["generation"] for call in session.delete.call_args_list] == ["1", "2"]
    assert all(call.args[0].endswith("fit%2F1%2F" + "a" * 64 + ".fit") for call in session.delete.call_args_list)
    assert session.get.call_args_list[0].kwargs["params"] == {
        "prefix": name,
        "versions": "true",
        "maxResults": "1000",
    }
    assert session.get.call_args_list[1].kwargs["params"]["pageToken"] == "synthetic-next-page"
    for call in [*session.get.call_args_list, *session.delete.call_args_list]:
        assert call.kwargs["allow_redirects"] is False
        assert call.kwargs["timeout"] == 15


@pytest.mark.parametrize(
    ("pages", "deletion_statuses"),
    [
        ([response(403)], ()),
        ([response(404)], ()),
        ([response(200, {"items": {}})], ()),
        ([response(200, {"items": [{"name": "export/1/synthetic.json"}]})], ()),
        ([response(200, {"items": [{"name": "export/1/synthetic.json", "generation": "1"}]})], (403,)),
        ([response(200, {"nextPageToken": "same"}), response(200, {"nextPageToken": "same"})], ()),
    ],
)
def test_failed_generation_cleanup_keeps_artifact_pending_for_retry(monkeypatch, pages, deletion_statuses):
    mock_storage(monkeypatch, pages, deletion_statuses)
    cipher = SimpleNamespace(decrypt=lambda content: b"synthetic-private/export/1/synthetic.json")
    monkeypatch.setattr(privacy_jobs, "push_cipher", lambda: cipher)
    artifact = SimpleNamespace(status="delete_pending", locator_enc="synthetic-ciphertext")
    db = SimpleNamespace(get=AsyncMock(return_value=artifact), delete=AsyncMock())
    job = SimpleNamespace(payload={"artifact_id": 1})
    with pytest.raises(RuntimeError, match="Private file cleanup failed; retry required"):
        asyncio.run(privacy_jobs.delete_artifact(db, job))
    db.delete.assert_not_awaited()
    assert artifact.locator_enc == "synthetic-ciphertext" and artifact.status == "delete_pending"


def test_successful_empty_inventory_is_idempotent_and_unknown_bucket_never_contacted(monkeypatch):
    session = mock_storage(monkeypatch, [response(200, {})], ())
    privacy_jobs._delete_storage_object("gcs", "synthetic-private/export/1/already-gone.json")
    session.delete.assert_not_called()
    session.get.reset_mock()
    with pytest.raises(RuntimeError, match="Invalid private storage locator"):
        privacy_jobs._delete_storage_object("gcs", "outside-allowlist/export/1/synthetic.json")
    session.get.assert_not_called()
