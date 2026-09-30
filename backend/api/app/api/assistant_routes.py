import hashlib
import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.assistant_schemas import ConfirmWrite, MessageCreate, ThreadCreate
from app.api.dependencies import current_user
from app.api.planning_routes import check_block
from app.api.product_schemas import ComplaintCreate
from app.api.schemas import WorkoutCreate
from app.core.config import settings
from app.core.database import get_db
from app.infrastructure.database.models import PrescribedWorkout, User
from app.infrastructure.database.models.product import (
    AssistantConfirmation,
    AssistantMessage,
    AssistantThread,
    Complaint,
    ReviewItem,
)
from app.services.access import require_athlete_access, require_role
from app.services.assistant import assistant_message_view, require_assistant_thread_access
from app.services.assistant_tools import ToolRead
from app.services.audit import add_audit

router = APIRouter(prefix="/assistant", tags=["Assistant"])


def stable_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def utc_aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def serialize_steps(value) -> list[dict]:
    return [group.model_dump(mode="json") for group in value]


async def owned_thread(db: AsyncSession, thread_id: int, user: User) -> AssistantThread:
    thread = await db.scalar(
        select(AssistantThread).where(
            AssistantThread.id == thread_id,
            AssistantThread.owner_id == user.id,
        )
    )
    if thread is None:
        raise HTTPException(404, "Conversación no encontrada")
    await require_assistant_thread_access(db, user, thread)
    return thread


@router.post("/threads", status_code=status.HTTP_201_CREATED)
async def create_thread(
    payload: ThreadCreate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_role(db, user, payload.role)
    scope = payload.athlete_scope_id
    if payload.role == "athlete":
        scope = user.id
    elif scope is not None:
        await require_athlete_access(db, user, scope)
    thread = AssistantThread(
        owner_id=user.id,
        role=payload.role,
        athlete_scope_id=scope,
        title=payload.title,
    )
    from app.services.provider_policy import require_provider_consent

    await require_provider_consent(db, user.id, "ai_assistant")
    db.add(thread)
    await db.commit()
    await db.refresh(thread)
    return {
        "id": thread.id,
        "role": thread.role,
        "athlete_scope_id": thread.athlete_scope_id,
        "title": thread.title,
    }


@router.post("/threads/{thread_id}/messages")
async def send_message(
    thread_id: int,
    payload: MessageCreate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    thread = await owned_thread(db, thread_id, user)
    from app.services.assistant_runtime import complete_run, prepare_run

    await db.refresh(thread, with_for_update=True)
    run, prepared = await prepare_run(db, user, thread, payload)
    if prepared is None:
        return run.result
    return await complete_run(db, user, thread, payload, run, prepared)


@router.post("/confirmations/{confirmation_id}")
async def confirm_write(
    confirmation_id: int,
    payload: ConfirmWrite,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    confirmation = await db.scalar(
        select(AssistantConfirmation)
        .where(
            AssistantConfirmation.id == confirmation_id,
            AssistantConfirmation.user_id == user.id,
        )
        .with_for_update()
    )
    if confirmation is None:
        raise HTTPException(404, "Confirmación no encontrada")
    await owned_thread(db, confirmation.thread_id, user)
    from app.services.provider_policy import require_provider_consent

    await require_provider_consent(db, user.id, "ai_assistant")
    athlete_id = int(confirmation.payload["athlete_id"])
    await require_provider_consent(db, athlete_id, "training_data_processing")
    await require_athlete_access(db, user, athlete_id)
    if confirmation.payload_hash != payload.payload_hash:
        raise HTTPException(409, "La vista previa cambió; vuelve a generarla")
    if confirmation.consumed_at is not None:
        return confirmation.result
    if utc_aware(confirmation.expires_at) < datetime.now(UTC):
        raise HTTPException(410, "La confirmación expiró")
    if confirmation.operation == "create_complaint":
        await require_role(db, user, "athlete")
        raw = {key: value for key, value in confirmation.payload.items() if key != "athlete_id"}
        parsed = ComplaintCreate.model_validate(raw)
        complaint = Complaint(athlete_id=athlete_id, **parsed.model_dump())
        db.add(complaint)
        await db.flush()
        db.add(
            ReviewItem(
                athlete_id=athlete_id,
                complaint_id=complaint.id,
                kind="complaint",
                priority="high" if complaint.limits_movement or complaint.intensity_0_10 >= 7 else "normal",
                reason="Molestia reportada y confirmada en el asistente",
                dedupe_key=f"complaint:{complaint.id}",
                status="open",
            )
        )
        from app.services.product_notifications import notify_assigned_coaches

        await notify_assigned_coaches(
            db,
            athlete_id=complaint.athlete_id,
            category="review",
            event_key=f"complaint:{complaint.id}:{complaint.version}",
            entity="complaint",
            entity_id=complaint.id,
            entity_version=complaint.version,
        )
        result = {"entity": "complaint", "id": complaint.id}
    elif confirmation.operation == "create_workout_draft":
        await require_role(db, user, "coach")
        raw = {key: value for key, value in confirmation.payload.items() if key != "athlete_id"}
        parsed = WorkoutCreate.model_validate(raw)
        await check_block(parsed.block_id, athlete_id, user.id, parsed.scheduled_date, db)
        workout = PrescribedWorkout(
            athlete_id=athlete_id,
            coach_id=user.id,
            title=parsed.title,
            description=parsed.description,
            scheduled_date=parsed.scheduled_date,
            sport_type=parsed.sport_type,
            block_id=parsed.block_id,
            steps=serialize_steps(parsed.steps),
        )
        db.add(workout)
        await db.flush()
        result = {"entity": "prescribed_workout", "id": workout.id, "status": "draft"}
    else:
        raise HTTPException(422, "Operación no soportada")
    confirmation.consumed_at = datetime.now(UTC)
    confirmation.result = result
    add_audit(
        db,
        actor_id=user.id,
        entity=result["entity"],
        entity_id=result["id"],
        action="assistant_confirmed_write",
    )
    await db.commit()
    return result


@router.get("/threads/{thread_id}/messages")
async def list_messages(
    thread_id: int,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await owned_thread(db, thread_id, user)
    rows = await db.scalars(
        select(AssistantMessage)
        .where(AssistantMessage.thread_id == thread_id)
        .order_by(AssistantMessage.created_at, AssistantMessage.id)
    )
    return [await assistant_message_view(db, user, item) for item in rows.all()]


@router.get("/threads")
async def list_threads(role: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    if role not in {"coach", "athlete"}:
        raise HTTPException(422, "Rol inválido")
    await require_role(db, user, role)
    rows = (
        await db.scalars(
            select(AssistantThread)
            .where(AssistantThread.owner_id == user.id, AssistantThread.role == role)
            .order_by(AssistantThread.id.desc())
            .limit(100)
        )
    ).all()
    result = []
    for thread in rows:
        try:
            await require_assistant_thread_access(db, user, thread)
        except HTTPException:
            continue
        result.append(
            {"id": thread.id, "title": thread.title, "role": thread.role, "athlete_scope_id": thread.athlete_scope_id}
        )
    return result


@router.post("/tools/read")
async def tool_read(
    payload: "ToolRead", role: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    from app.services.assistant_tools import read_tool

    if role not in {"coach", "athlete"}:
        raise HTTPException(422, "Rol inválido")
    await require_role(db, user, role)
    from app.services.provider_policy import require_provider_consent

    await require_provider_consent(db, user.id, "ai_assistant")
    return await read_tool(db, user, payload, role)


@router.get("/threads/{thread_id}/confirmations")
async def list_confirmations(thread_id: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await owned_thread(db, thread_id, user)
    from app.services.assistant_runtime import confirmation_view

    rows = (
        await db.scalars(
            select(AssistantConfirmation).where(
                AssistantConfirmation.thread_id == thread_id,
                AssistantConfirmation.user_id == user.id,
                AssistantConfirmation.consumed_at.is_(None),
                AssistantConfirmation.expires_at > datetime.now(UTC),
            )
        )
    ).all()
    return [confirmation_view(c) for c in rows]


@router.post("/runs/{run_id}/cancel")
async def cancel_run(run_id: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    from sqlalchemy import update

    from app.infrastructure.database.models.providers import AssistantRun

    run = await db.scalar(select(AssistantRun).where(AssistantRun.id == run_id, AssistantRun.user_id == user.id))
    if not run:
        raise HTTPException(404, "Petición no encontrada")
    await owned_thread(db, run.thread_id, user)
    await db.execute(
        update(AssistantRun)
        .where(AssistantRun.id == run.id, AssistantRun.status == "running")
        .values(status="cancelled")
    )
    await db.commit()
    return {"run_id": run.id, "status": run.status}


@router.post("/threads/{thread_id}/messages/stream")
async def stream_message(
    thread_id: int, payload: MessageCreate, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    import asyncio

    from fastapi.responses import StreamingResponse

    from app.services.assistant_runtime import complete_run, prepare_run

    thread = await owned_thread(db, thread_id, user)
    await db.refresh(thread, with_for_update=True)
    run, prepared = await prepare_run(db, user, thread, payload)

    async def events():
        yield "data: " + json.dumps({"type": "run", "run_id": run.id}) + "\n\n"
        try:
            result = run.result if prepared is None else await complete_run(db, user, thread, payload, run, prepared)
            # Publish validated complete answer only, not untrusted token fragments.
            yield "data: " + json.dumps({"type": "result", "result": result}, ensure_ascii=False) + "\n\n"
        except HTTPException as exc:
            yield "data: " + json.dumps({"type": "error", "detail": exc.detail}) + "\n\n"
        except asyncio.CancelledError:
            return

    return StreamingResponse(
        events(), media_type="text/event-stream", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"}
    )


@router.get("/status")
async def assistant_status(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    from app.infrastructure.database.models.providers import AssistantBudget
    from app.services.access import primary_organization_id

    org = await primary_organization_id(db, user.id)
    month = datetime.now(UTC).date().replace(day=1)
    user_budget = await db.scalar(
        select(AssistantBudget).where(
            AssistantBudget.scope == "user", AssistantBudget.scope_id == user.id, AssistantBudget.month == month
        )
    )
    org_budget = await db.scalar(
        select(AssistantBudget).where(
            AssistantBudget.scope == "organization", AssistantBudget.scope_id == org, AssistantBudget.month == month
        )
    )

    def view(budget):
        return {
            "requests": budget.requests if budget else 0,
            "tokens": budget.tokens if budget else 0,
            "estimated_cost_microusd": budget.cost_microusd if budget else 0,
        }

    return {
        "provider": settings.AI_PROVIDER,
        "model": settings.AI_MODEL if settings.AI_PROVIDER == "vertex" else "deterministic-pilot-v1",
        "user_usage": view(user_budget),
        "organization_usage": view(org_budget),
        "manual_available": True,
        "month": month.isoformat(),
    }
