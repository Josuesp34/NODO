from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.infrastructure.database.models import User
from app.infrastructure.database.models.product import (
    CoachAthleteAssignment,
    CommercialPlan,
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


async def require_athlete_access(db: AsyncSession, user: User, athlete_id: int) -> User:
    athlete = await db.get(User, athlete_id)
    if athlete is None or athlete.deleted_at is not None:
        raise HTTPException(404, "Atleta no encontrado")
    if user.is_superuser:
        return athlete
    if user.id == athlete_id:
        await require_role(db, user, "athlete")
        return athlete
    assignment = await db.scalar(
        select(CoachAthleteAssignment.id).where(
            CoachAthleteAssignment.coach_id == user.id,
            CoachAthleteAssignment.athlete_id == athlete_id,
            CoachAthleteAssignment.status == "active",
        )
    )
    if assignment is None:
        raise HTTPException(404, "Atleta no encontrado")
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
    subscription = await db.scalar(
        select(Subscription).where(
            Subscription.organization_id == organization_id,
            Subscription.status == "active",
        )
    )
    if subscription is None:
        if settings.ENVIRONMENT != "development":
            raise HTTPException(402, "La organización no tiene una suscripción activa")
        return
    plan = await db.get(CommercialPlan, subscription.plan_id)
    active_count = await db.scalar(
        select(func.count(CoachAthleteAssignment.id)).where(
            CoachAthleteAssignment.organization_id == organization_id,
            CoachAthleteAssignment.status == "active",
        )
    )
    if plan is None or active_count >= plan.athlete_limit:
        raise HTTPException(409, "Se alcanzó el cupo de atletas del plan")
