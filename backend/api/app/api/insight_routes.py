from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import current_coach, current_superuser, current_user
from app.api.insight_schemas import CompetitionScenarios
from app.core.config import settings
from app.core.database import get_db
from app.domain.scenarios import FORMULA_VERSION, LIMITS, project_loads
from app.infrastructure.database.models import User
from app.infrastructure.database.models.product import (
    CoachAthleteAssignment,
    Competition,
    Complaint,
    DailyLoad,
    Organization,
    OrganizationMembership,
    UserRoleAssignment,
)
from app.infrastructure.database.models.providers import AssistantBudget, AssistantRun
from app.services.access import require_athlete_access

router = APIRouter(tags=["Product insights"])


@router.post("/athletes/{athlete_id}/competitions/{competition_id}/scenarios")
async def competition_scenarios(
    athlete_id: int,
    competition_id: int,
    payload: CompetitionScenarios,
    coach: User = Depends(current_coach),
    db: AsyncSession = Depends(get_db),
):
    athlete = await require_athlete_access(db, coach, athlete_id)
    if coach.id == athlete_id and not coach.is_superuser:
        raise HTTPException(403, "Los escenarios del plan requieren al entrenador asignado")
    competition = await db.scalar(
        select(Competition).where(
            Competition.id == competition_id,
            Competition.athlete_id == athlete_id,
            Competition.coach_id == coach.id,
        )
    )
    if competition is None:
        raise HTTPException(404, "Competencia no encontrada")
    if competition.version != payload.expected_competition_version:
        raise HTTPException(409, "La competencia cambió; recarga antes de comparar")
    count = (competition.competition_date - payload.start_date).days + 1
    if not 1 <= count <= 42:
        raise HTTPException(422, "El escenario debe cubrir entre 1 y 42 días hasta la competencia")
    if any(len(alternative.daily_loads) != count for alternative in payload.alternatives):
        raise HTTPException(422, "Indica una carga explícita por día, hasta la fecha de competencia inclusive")
    if any(not item.name.strip() for item in payload.alternatives) or len(
        {item.name.strip().casefold() for item in payload.alternatives}
    ) != len(payload.alternatives):
        raise HTTPException(422, "Cada alternativa requiere un nombre distinto")
    previous_day = payload.start_date - timedelta(days=1)
    previous = await db.scalar(
        select(DailyLoad).where(
            DailyLoad.athlete_id == athlete_id,
            DailyLoad.local_date == previous_day,
            DailyLoad.load_unit == payload.load_unit,
            DailyLoad.formula_version == FORMULA_VERSION,
        )
    )
    if payload.initial_state:
        baseline = {
            "ctl": payload.initial_state.ctl,
            "atl": payload.initial_state.atl,
            "source": "explicit_coach_assumption",
            "explanation": payload.initial_state.explanation,
            "local_date": previous_day,
            "load_unit": payload.load_unit,
        }
    elif previous:
        baseline = {
            "ctl": previous.ctl,
            "atl": previous.atl,
            "source": "persisted_daily_load",
            "explanation": "Estado guardado al cierre del día anterior; incluye las hipótesis del recálculo existente.",
            "local_date": previous.local_date,
            "load_unit": previous.load_unit,
            "recomputed_at": previous.recomputed_at,
        }
    else:
        baseline = None
    complaints = await db.scalar(
        select(func.count())
        .select_from(Complaint)
        .where(Complaint.athlete_id == athlete_id, Complaint.status != "closed")
    )
    alternatives = []
    for item in payload.alternatives:
        try:
            # Validate inputs even with missing baseline; missing state never becomes a zero baseline.
            rows = project_loads(
                item.daily_loads, baseline["ctl"] if baseline else 0, baseline["atl"] if baseline else 0
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        if not baseline:
            rows = [{"load": load, "ctl": None, "atl": None, "tsb": None} for load in item.daily_loads]
        alternatives.append(
            {
                "name": item.name.strip(),
                "load_unit": payload.load_unit,
                "formula_version": FORMULA_VERSION,
                "total_assumed_load": sum(item.daily_loads),
                "competition_day_start_tsb": rows[-1]["tsb"],
                "days": [
                    {"local_date": payload.start_date + timedelta(days=index), **row} for index, row in enumerate(rows)
                ],
                "assumptions": LIMITS,
                "initial_state": baseline,
            }
        )
    return {
        "status": "projected" if baseline else "insufficient_initial_state",
        "competition": {"id": competition.id, "version": competition.version, "date": competition.competition_date},
        "timezone": athlete.timezone,
        "load_unit": payload.load_unit,
        "formula_version": FORMULA_VERSION,
        "initial_state": baseline,
        "unresolved_complaints": complaints,
        "review_note": "Hay molestias en seguimiento; este cálculo no autoriza entrenar." if complaints else None,
        "alternatives": alternatives,
        "limits": LIMITS,
    }


def month_bounds(month):
    month = month or datetime.now(UTC).date().replace(day=1)
    if month.day != 1 or not 2000 <= month.year <= 2100:
        raise HTTPException(422, "El período requiere el primer día del mes UTC")
    start = datetime(month.year, month.month, 1, tzinfo=UTC)
    end = (start + timedelta(days=32)).replace(day=1)
    return month, start, end


async def ai_cost_report(db, *, month, user_id=None):
    month, start, end = month_bounds(month)
    query = (
        select(
            AssistantRun.user_id,
            AssistantRun.status,
            func.count(AssistantRun.id),
            func.sum(AssistantRun.input_tokens),
            func.sum(AssistantRun.output_tokens),
            func.sum(AssistantRun.cost_microusd),
        )
        .where(AssistantRun.created_at >= start, AssistantRun.created_at < end)
        .group_by(AssistantRun.user_id, AssistantRun.status)
    )
    if user_id is not None:
        query = query.where(AssistantRun.user_id == user_id)
    data = (await db.execute(query)).all()
    owners = {row[0] for row in data}
    if user_id is not None:
        owners.add(user_id)
    budgets_query = select(AssistantBudget).where(
        AssistantBudget.month == month, AssistantBudget.scope.in_(["user", "organization"])
    )
    if user_id is not None:
        budgets_query = budgets_query.where(AssistantBudget.scope == "user", AssistantBudget.scope_id == user_id)
    budgets = (await db.scalars(budgets_query)).all()
    owners.update(row.scope_id for row in budgets if row.scope == "user")
    users = (await db.scalars(select(User).where(User.id.in_(owners)))).all() if owners else []
    roles = (
        (
            await db.execute(
                select(UserRoleAssignment.user_id, UserRoleAssignment.role).where(
                    UserRoleAssignment.user_id.in_(owners)
                )
            )
        ).all()
        if owners
        else []
    )
    rows = {
        user.id: {
            "user_id": user.id,
            "name": f"{user.first_name} {user.last_name}",
            "roles": sorted(role for identifier, role in roles if identifier == user.id),
            "completed_requests": 0,
            "completed_input_tokens": 0,
            "completed_output_tokens": 0,
            "estimated_completed_microusd": 0,
            "in_flight_reserved_microusd": 0,
            "uncertain_reserved_microusd": 0,
        }
        for user in users
        if user.deleted_at is None
    }
    for identifier, status, count, input_tokens, output_tokens, cost in data:
        if identifier not in rows:
            continue
        row = rows[identifier]
        if status == "completed":
            row["completed_requests"] += count
            row["completed_input_tokens"] += input_tokens or 0
            row["completed_output_tokens"] += output_tokens or 0
            row["estimated_completed_microusd"] += cost or 0
        else:
            key = "in_flight_reserved_microusd" if status in {"running", "pending"} else "uncertain_reserved_microusd"
            row[key] += cost or 0
    limits = []
    for budget in budgets:
        if budget.scope == "user" and budget.scope_id not in rows:
            continue
        organization_scope = budget.scope == "organization"
        ceiling = settings.AI_ORG_MONTHLY_BUDGET_USD if organization_scope else settings.AI_USER_MONTHLY_BUDGET_USD
        limit = {
            "scope": budget.scope,
            "scope_id": budget.scope_id,
            "requests": budget.requests,
            "tokens": budget.tokens,
            "used_or_reserved_microusd": budget.cost_microusd,
            "limit_microusd": int(ceiling * 1000000),
        }
        if organization_scope:
            organization = await db.get(Organization, budget.scope_id)
            athletes = await db.scalar(
                select(func.count(func.distinct(CoachAthleteAssignment.athlete_id))).where(
                    CoachAthleteAssignment.organization_id == budget.scope_id, CoachAthleteAssignment.status == "active"
                )
            )
            coaches = await db.scalar(
                select(func.count(func.distinct(OrganizationMembership.user_id)))
                .join(UserRoleAssignment, UserRoleAssignment.user_id == OrganizationMembership.user_id)
                .where(
                    OrganizationMembership.organization_id == budget.scope_id,
                    OrganizationMembership.status == "active",
                    UserRoleAssignment.role == "coach",
                )
            )
            limit.update(
                {
                    "name": organization.name if organization else "Organización retirada",
                    "active_athletes": athletes,
                    "active_coaches": coaches,
                    "budget_usage_per_active_athlete_microusd": budget.cost_microusd / athletes if athletes else None,
                    "budget_usage_per_active_coach_microusd": budget.cost_microusd / coaches if coaches else None,
                }
            )
        limits.append(limit)
    summable = [
        "completed_requests",
        "completed_input_tokens",
        "completed_output_tokens",
        "estimated_completed_microusd",
        "in_flight_reserved_microusd",
        "uncertain_reserved_microusd",
    ]
    return {
        "month_utc": month,
        "currency": "USD",
        "unit": "microusd",
        "totals": {key: sum(row[key] for row in rows.values()) for key in summable},
        "users": sorted(rows.values(), key=lambda row: row["user_id"]),
        "budgets": limits,
        "pricing_current": {
            "provider": settings.AI_PROVIDER,
            "model": settings.AI_MODEL,
            "input_usd_per_million": settings.AI_INPUT_USD_PER_MILLION,
            "output_usd_per_million": settings.AI_OUTPUT_USD_PER_MILLION,
        },
        "explanation": (
            "Estimaciones guardadas y reservas conservadoras; no son facturas del proveedor. "
            "Se suma cada run una vez por usuario. Los presupuestos de usuario y organización "
            "se presentan por separado y no se suman entre sí. Fallos/cancelaciones conservan "
            "reserva por consumo externo no confirmado."
        ),
        "pricing_note": (
            "La configuración visible es actual; no atribuye modelo o tarifa históricos a ejecuciones anteriores."
        ),
        "allocation_note": (
            "Los denominadores de atleta y coach son miembros activos actuales, no una fotografía del mes elegido. "
            "El reparto de uso presupuestario incluye reservas y no atribuye una factura individual."
        ),
    }


@router.get("/admin/commercial/ai-costs")
async def admin_ai_costs(
    month: date | None = Query(default=None),
    admin: User = Depends(current_superuser),
    db: AsyncSession = Depends(get_db),
):
    return await ai_cost_report(db, month=month)


@router.get("/account/ai-costs")
async def own_ai_costs(
    month: date | None = Query(default=None),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ai_cost_report(db, month=month, user_id=user.id)
