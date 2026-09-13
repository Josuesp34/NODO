from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import configure_mappers

from app.api import routes
from app.core.config import settings
from app.core.database import get_db
from app.infrastructure.database.models import Base
from app.main import get_application
from app.services.data_processing import clean_telemetry_to_dataframe
from app.services.physiology import extract_session_metrics


class FakeSession:
    def __init__(self):
        self.activity = None
        self.telemetry = []
        self.flush = AsyncMock()
        self.commit = AsyncMock()
        self.rollback = AsyncMock()
        self.execute = AsyncMock(return_value=MagicMock())

    def add(self, activity):
        self.activity = activity
        activity.id = 123

    def add_all(self, telemetry):
        self.telemetry = telemetry


@pytest.fixture
def api():
    app = get_application()
    db = FakeSession()

    async def override():
        yield db

    app.dependency_overrides[get_db] = override
    with TestClient(app) as client:
        yield client, db


@pytest.fixture
def decoded(monkeypatch):
    df = clean_telemetry_to_dataframe([
        {"timestamp": "2026-09-01T00:00:00Z", "heart_rate": 150},
        {"timestamp": "2026-09-01T00:00:10Z", "heart_rate": None},
    ])
    metrics = extract_session_metrics(df, {"total_timer_time": 8, "avg_heart_rate": 150})
    monkeypatch.setattr(routes, "parse_fit", lambda _: (df, metrics))


def upload(client, name="sample.fit", content=b"sample", **kwargs):
    return client.post("/api/v1/upload-fit/", files={"file": (name, content)}, **kwargs)


def test_all_models_registered_and_mappers_resolve():
    configure_mappers()
    assert set(Base.metadata.tables) == {"users", "activities", "telemetry_records", "prescribed_workouts", "daily_physiology"}


def test_bad_extension_and_invalid_binary_keep_400(api):
    client, db = api
    assert upload(client, name="sample.txt").status_code == 400
    assert upload(client, content=b"not a fit file").status_code == 400
    db.commit.assert_not_awaited()


def test_large_file_returns_413(api, monkeypatch):
    monkeypatch.setattr(settings, "MAX_FIT_BYTES", 3)
    assert upload(api[0], content=b"1234").status_code == 413


def test_import_preserves_missing_sensors_and_does_not_assume_profile(api, decoded):
    client, db = api
    response = upload(client, name="SAMPLE.FIT")
    assert response.status_code == 200
    assert response.json()["session_analytics"]["trimp_score"] is None
    assert db.activity.total_duration_sec == 8
    assert db.telemetry[1].heart_rate is None
    assert db.telemetry[0].power is None
    db.commit.assert_awaited_once()


def test_explicit_profile_calculates_trimp(api, decoded):
    response = upload(api[0], data={"rest_hr": 50, "max_hr": 200, "is_male": "true"})
    assert response.status_code == 200
    assert response.json()["session_analytics"]["trimp_score"] > 0


@pytest.mark.parametrize("data", [{"rest_hr": 50}, {"rest_hr": 100, "max_hr": 100, "is_male": "true"}])
def test_partial_or_invalid_profile_is_422(api, decoded, data):
    assert upload(api[0], data=data).status_code == 422
    api[1].commit.assert_not_awaited()


def test_database_failure_rolls_back_without_exposing_details(api, decoded):
    client, db = api
    db.flush.side_effect = RuntimeError("private database detail")
    response = upload(client)
    assert response.status_code == 500
    assert "private" not in response.text
    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()


def test_ingest_disabled_outside_development(api, monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    assert upload(api[0]).status_code == 503


def test_health_is_read_only(api):
    client, db = api
    db.execute.return_value.scalar.return_value = "2.x"
    assert client.get("/health").status_code == 200
    assert str(db.execute.call_args.args[0]).startswith("SELECT")
    db.commit.assert_not_awaited()


def test_health_failure_returns_503(api):
    client, db = api
    db.execute.side_effect = RuntimeError("private connection detail")
    response = client.get("/health")
    assert response.status_code == 503
    assert "private" not in response.text


def test_health_missing_extension_returns_503(api):
    client, db = api
    db.execute.return_value.scalar.return_value = None
    assert client.get("/health").status_code == 503
    db.commit.assert_not_awaited()
