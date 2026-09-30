from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import configure_mappers

from app.core.database import get_db
from app.infrastructure.database.models import Base
from app.main import get_application


class FakeSession:
    def __init__(self):
        self.commit = AsyncMock()
        self.execute = AsyncMock(return_value=MagicMock())


@pytest.fixture
def api():
    app = get_application()
    db = FakeSession()

    async def override():
        yield db

    app.dependency_overrides[get_db] = override
    with TestClient(app) as client:
        yield client, db


def test_all_pilot_models_are_registered_and_mappers_resolve():
    configure_mappers()
    required = {
        "users",
        "user_roles",
        "organizations",
        "coach_athlete_assignments",
        "activities",
        "activity_laps",
        "telemetry_records",
        "daily_load",
        "observations",
        "checkins",
        "complaints",
        "review_items",
        "jobs",
        "assistant_threads",
        "assistant_confirmations",
        "recommendations",
        "commercial_plans",
        "subscriptions",
        "managed_payments",
    }
    assert required <= set(Base.metadata.tables)


def test_legacy_unauthenticated_ingest_is_closed(api):
    response = api[0].post(
        "/api/v1/upload-fit/",
        files={"file": ("sample.fit", b"sample")},
    )
    assert response.status_code == 410
    assert "/athletes/{athlete_id}/activities/fit" in response.json()["detail"]


def test_health_is_read_only_postgres_check(api):
    client, db = api
    db.execute.return_value.scalar.return_value = 1
    assert client.get("/health").status_code == 200
    assert str(db.execute.call_args.args[0]) == "SELECT 1"
    db.commit.assert_not_awaited()


def test_health_failure_returns_503_without_internal_detail(api):
    client, db = api
    db.execute.side_effect = RuntimeError("private connection detail")
    response = client.get("/health")
    assert response.status_code == 503
    assert "private" not in response.text


def test_health_unexpected_result_returns_503(api):
    client, db = api
    db.execute.return_value.scalar.return_value = None
    assert client.get("/health").status_code == 503
