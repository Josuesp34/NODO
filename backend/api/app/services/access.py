from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.infrastructure.database.models import User
from app.infrastructure.database.models.product import (
    CoachAthleteAssignment,
    CommercialPlan,
    Organization,
    OrganizationMembership,
    Subscription,
    UserRoleAssignment,
)

CAPABILITIES = {
    "coach": ["coach:calendar", "coach:athletes", "coach:review", "coach:assistant"],
    "athlete": ["athlete:today", "athlete:data", "athlete:checkin", "athlete:assistant"],
}


async def roles_for(db: AsyncSession, user_id: int) -> list[str]:
    result = await db.scalars(select(UserRoleAssignment.role).where(UserRoleAssignment.user_id == user_id))
    return sorted(set(result.all()))


async def organization_ids_for(db: AsyncSession, user_id: int) -> list[int]:
    result = await db.scalars(
        select(OrganizationMembership.organization_id).where(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.status == "active",
        )
    )
    return sorted(set(result.all()))


async def capabilities_for(db: AsyncSession, user: User) -> list[str]:
    roles = await roles_for(db, user.id)
    capabilities = {item for role in roles for item in CAPABILITIES.get(role, [])}
    if user.is_superuser:
        capabilities.add("platform:admin")
    return sorted(capabilities)


async def require_role(db: AsyncSession, user: User, role: str) -> None:
    if user.is_superuser:
        return
    assigned = await db.scalar(
        select(UserRoleAssignment.id).where(
            UserRoleAssignment.user_id == user.id,
            UserRoleAssignment.role == role,
        )
    )
    if assigned is None:
        raise HTTPException(403, f"Esta acción requiere rol {role}")
    if role == "coach":
        await require_organization_active(db, user.id)


async def require_athlete_access(db: AsyncSession, user: User, athlete_id: int) -> User:
    athlete = await db.scalar(
        select(User).where(User.id == athlete_id).with_for_update().execution_options(populate_existing=True)
    )
    if athlete is None or athlete.deleted_at is not None:
        raise HTTPException(404, "Atleta no encontrado")
    from app.services.privacy import require_processing_consent

    if user.is_superuser:
        await require_processing_consent(db, athlete_id, "training_data_processing")
        return athlete
    if user.id == athlete_id:
        await require_role(db, user, "athlete")
        await require_processing_consent(db, athlete_id, "training_data_processing")
        return athlete
    assignment = await db.scalar(
        select(CoachAthleteAssignment).where(
            CoachAthleteAssignment.coach_id == user.id,
            CoachAthleteAssignment.athlete_id == athlete_id,
            CoachAthleteAssignment.status == "active",
        )
    )
    if assignment is None:
        raise HTTPException(404, "Atleta no encontrado")
    await require_role(db, user, "coach")
    await require_organization_active(db, user.id, organization_id=assignment.organization_id)
    await require_processing_consent(db, athlete_id, "training_data_processing")
    return athlete


async def has_athlete_access(db: AsyncSession, user: User, athlete_id: int) -> bool:
    try:
        await require_athlete_access(db, user, athlete_id)
    except HTTPException as exc:
        if exc.status_code not in {403, 404}:
            raise
        return False
    return True


async def primary_organization_id(db: AsyncSession, user_id: int) -> int:
    organization_id = await db.scalar(
        select(OrganizationMembership.organization_id)
        .where(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.status == "active",
        )
        .order_by(OrganizationMembership.id)
        .limit(1)
    )
    if organization_id is None:
        raise HTTPException(409, "La cuenta no pertenece a una organización")
    return organization_id


async def enforce_athlete_capacity(db: AsyncSession, coach_id: int, organization_id: int) -> None:
    # Serialize invitations across coaches in the same organization.
    organization = await db.scalar(select(Organization).where(Organization.id == organization_id).with_for_update())
    if organization is None or organization.status != "active":
        raise HTTPException(403, "La organización está suspendida")
    today = datetime.now(UTC).date()
    subscription = await db.scalar(select(Subscription).where(Subscription.organization_id == organization_id))
    if subscription is None:
        if settings.ENVIRONMENT == "development":
            return
        raise HTTPException(402, "La organización no tiene una suscripción activa")
    if (
        subscription.status != "active"
        or subscription.starts_on > today
        or (subscription.ends_on and subscription.ends_on < today)
    ):
        raise HTTPException(402, "La suscripción está suspendida o vencida")
    plan = await db.get(CommercialPlan, subscription.plan_id)
    active_count = await db.scalar(
        select(func.count(func.distinct(CoachAthleteAssignment.athlete_id))).where(
            CoachAthleteAssignment.organization_id == organization_id,
            CoachAthleteAssignment.status == "active",
        )
    )
    if plan is None or not plan.active or active_count >= plan.athlete_limit:
        raise HTTPException(409, "Se alcanzó el cupo de atletas del plan")


async def require_organization_active(db: AsyncSession, user_id: int, *, organization_id: int | None = None) -> None:
    query = (
        select(Organization, Subscription)
        .join(OrganizationMembership, OrganizationMembership.organization_id == Organization.id)
        .outerjoin(Subscription, Subscription.organization_id == Organization.id)
        .where(OrganizationMembership.user_id == user_id, OrganizationMembership.status == "active")
    )
    if organization_id is not None:
        query = query.where(Organization.id == organization_id)
    rows = (await db.execute(query.execution_options(populate_existing=True))).all()
    if not rows:
        if settings.ENVIRONMENT == "development" and organization_id is None:
            return
        raise HTTPException(403, "La cuenta no pertenece a una organización activa")
    today = datetime.now(UTC).date()
    for organization, subscription in rows:
        if organization.status != "active":
            continue
        if subscription is None and settings.ENVIRONMENT == "development":
            return
        if (
            subscription
            and subscription.status == "active"
            and subscription.starts_on <= today
            and (subscription.ends_on is None or subscription.ends_on >= today)
        ):
            return
    raise HTTPException(403, "La organización o suscripción está suspendida o vencida")
