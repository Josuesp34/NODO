from fastapi import HTTPException
from sqlalchemy import select

from app.core.config import settings
from app.infrastructure.database.models import User
from app.infrastructure.database.models.product import Consent


async def require_provider_consent(db, user_id: int, scope: str) -> None:
    """Same pilot-v1 policy as privacy; explicit revocation always wins."""
    person = await db.scalar(
        select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True)
    )
    if person is None or person.deleted_at is not None:
        raise HTTPException(404, "Cuenta no disponible")
    from app.services import access

    organization_guard = getattr(access, "require_organization_active", None)
    if organization_guard is not None:
        await organization_guard(db, user_id)
    consent = await db.scalar(
        select(Consent).where(Consent.user_id == user_id, Consent.scope == scope, Consent.version == "pilot-v1")
    )
    if (consent and consent.revoked_at is not None) or (not consent and settings.ENVIRONMENT != "development"):
        raise HTTPException(403, f"CONSENT_REQUIRED:{scope}")
