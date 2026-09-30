import asyncio
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.schemas import CoachRegistration
from app.bootstrap_admin import create_first_admin, run
from app.core.security import verify_password
from app.infrastructure.database.models import Base, User
from app.infrastructure.database.models.product import AuditLog, UserRoleAssignment


def test_first_admin_bootstrap_is_idempotent_and_never_adds_another_admin():
    async def scenario():
        engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        payload = CoachRegistration(
            email="admin-demo@example.com", password="Synthetic-admin-password", first_name="Demo", last_name="Admin"
        )
        async with sessions() as db:
            admin_id = await create_first_admin(db, payload)
            assert await create_first_admin(db, payload) == admin_id
            user = await db.get(User, admin_id)
            assert user.is_superuser and verify_password(payload.password, user.hashed_password)
            assert await db.scalar(select(func.count()).select_from(User)) == 1
            assert await db.scalar(select(func.count()).select_from(UserRoleAssignment)) == 1
            assert await db.scalar(select(func.count()).select_from(AuditLog)) == 1
            other = payload.model_copy(update={"email": "another-demo@example.com"})
            with pytest.raises(ValueError, match="Ya existe"):
                await create_first_admin(db, other)
            assert await db.scalar(select(func.count()).select_from(User)) == 1
        await engine.dispose()

    asyncio.run(scenario())


def test_bootstrap_requires_explicit_job_confirmation_before_credentials(monkeypatch):
    monkeypatch.delenv("NODO_BOOTSTRAP_CONFIRM", raising=False)
    monkeypatch.delenv("NODO_BOOTSTRAP_PASSWORD", raising=False)
    with pytest.raises(ValueError, match="confirmación explícita"):
        asyncio.run(run())


def test_bootstrap_configuration_failure_does_not_print_secret_inputs(tmp_path):
    synthetic_secret = "synthetic-bootstrap-secret-must-not-appear"
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(Path(__file__).resolve().parents[2]),
        "NODO_BOOTSTRAP_CONFIRM": "CREATE-FIRST-ADMIN",
        "NODO_BOOTSTRAP_EMAIL": "admin-demo@example.com",
        "NODO_BOOTSTRAP_PASSWORD": "Synthetic-admin-password",
        "NODO_BOOTSTRAP_FIRST_NAME": "Demo",
        "NODO_BOOTSTRAP_LAST_NAME": "Admin",
        "RESEND_API_KEY": synthetic_secret,
    }
    # A clean cwd prevents a developer .env from hiding missing DATABASE_URL.
    result = subprocess.run(
        [sys.executable, "-m", "app.bootstrap_admin"], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30
    )
    output = result.stdout + result.stderr
    assert result.returncode != 0 and "Bootstrap fallido" in output
    assert synthetic_secret not in output and "Traceback" not in output
