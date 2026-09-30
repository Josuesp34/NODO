"""One-off first-admin job. Credentials come from runtime secrets, never CLI arguments."""

import asyncio
import os
import secrets

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import CoachRegistration
from app.infrastructure.database.models import User
from app.infrastructure.database.models.product import Organization, OrganizationMembership, UserRoleAssignment
from app.infrastructure.database.models.user import UserRole
from app.services.audit import add_audit


async def create_first_admin(db: AsyncSession, payload: CoachRegistration) -> int:
    from app.core.security import hash_password

    if db.bind and db.bind.dialect.name == "postgresql":
        # Serialize competing one-off jobs; do not silently create two first administrators.
        await db.execute(text("SELECT pg_advisory_xact_lock(781304901)"))
    admin = await db.scalar(select(User).where(User.is_superuser.is_(True), User.deleted_at.is_(None)))
    if admin is not None:
        if admin.email == str(payload.email).lower():
            return admin.id
        raise ValueError("Ya existe un administrador; usar el procedimiento de acceso vigente.")
    if await db.scalar(select(User).where(User.email == str(payload.email).lower())):
        raise ValueError("La cuenta ya existe; el bootstrap no eleva cuentas existentes.")
    user = User(
        email=payload.email,
        first_name=payload.first_name,
        last_name=payload.last_name,
        timezone=payload.timezone,
        role=UserRole.COACH,
        is_superuser=True,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    await db.flush()
    organization = Organization(name="Administración NODO", slug=f"platform-admin-{secrets.token_hex(6)}")
    db.add(organization)
    await db.flush()
    db.add(UserRoleAssignment(user_id=user.id, role="coach"))
    db.add(OrganizationMembership(organization_id=organization.id, user_id=user.id, role="owner", status="active"))
    add_audit(db, actor_id=user.id, entity="user", entity_id=user.id, action="bootstrap_first_admin")
    await db.commit()
    return user.id


async def run() -> None:
    if os.environ.get("NODO_BOOTSTRAP_CONFIRM") != "CREATE-FIRST-ADMIN":
        raise ValueError("El bootstrap exige confirmación explícita en el job autorizado.")
    payload = CoachRegistration(
        email=os.environ["NODO_BOOTSTRAP_EMAIL"],
        password=os.environ["NODO_BOOTSTRAP_PASSWORD"],
        first_name=os.environ["NODO_BOOTSTRAP_FIRST_NAME"],
        last_name=os.environ["NODO_BOOTSTRAP_LAST_NAME"],
        timezone=os.environ.get("NODO_BOOTSTRAP_TIMEZONE", "UTC"),
    )
    # Settings/engine initialization can fail with secret-bearing validation inputs.
    # Keep these imports inside the protected entrypoint rather than module import time.
    from app.core.database import async_session_maker

    async with async_session_maker() as db:
        await create_first_admin(db, payload)
    print("Bootstrap del primer administrador completado. No se imprimen credenciales.")


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except Exception:
        # Validation/driver errors can contain passwords or URLs. Do not log their inputs.
        raise SystemExit("Bootstrap fallido: verificar datos, permisos, migración y administrador existente.") from None
