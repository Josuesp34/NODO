import hashlib
import json
from datetime import UTC, datetime, timedelta

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
from app.services.assistant import SimulatedAssistant
from app.services.audit import add_audit

router = APIRouter(prefix="/assistant", tags=["Assistant"])


def stable_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def utc_aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def serialize_steps(value) -> list[dict]:
    return [group.model_dump(mode="json") for group in value]


async def owned_thread(db: AsyncSession, thread_id: int, user_id: int) -> AssistantThread:
    thread = await db.scalar(
        select(AssistantThread).where(
            AssistantThread.id == thread_id,
            AssistantThread.owner_id == user_id,
        )
    )
    if thread is None:
        raise HTTPException(404, "Conversación no encontrada")
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
    db.add(thread)
    await db.commit()
    await db.refresh(thread)
    return {
        "id": thread.id,
        "role": thread.role,
        "athlete_scope_id": thread.athlete_scope_id,
        "title": thread.title,
    }


async def read_facts(db: AsyncSession, thread: AssistantThread, question: str) -> tuple[list[str], list[dict]]:
    facts: list[str] = []
    citations: list[dict] = []
    if thread.role == "coach" and "revisi" in question.lower():
        rows = (
            await db.scalars(
                select(ReviewItem)
                .where(ReviewItem.status.in_(["open", "follow_up"]))
                .order_by(ReviewItem.priority.desc())
                .limit(20)
            )
        ).all()
        for item in rows:
            try:
                await require_athlete_access(db, await db.get(User, thread.owner_id), item.athlete_id)
            except HTTPException:
                continue
            facts.append(f"Atleta {item.athlete_id}: {item.reason}.")
            citations.append(
                {
                    "entity": "review_item",
                    "id": item.id,
                    "athlete_id": item.athlete_id,
                    "source": "nodo",
                }
            )
    elif thread.athlete_scope_id is not None:
        workouts = (
            await db.scalars(
                select(PrescribedWorkout)
                .where(
                    PrescribedWorkout.athlete_id == thread.athlete_scope_id,
                    PrescribedWorkout.status == "published",
                )
                .order_by(PrescribedWorkout.scheduled_date)
                .limit(14)
            )
        ).all()
        for workout in workouts:
            facts.append(f"{workout.scheduled_date.date()}: {workout.title} ({workout.sport_type}).")
            citations.append(
                {
                    "entity": "prescribed_workout",
                    "id": workout.id,
                    "athlete_id": workout.athlete_id,
                    "date": str(workout.scheduled_date.date()),
                    "source": "nodo",
                }
            )
    return facts, citations


@router.post("/threads/{thread_id}/messages")
async def send_message(
    thread_id: int,
    payload: MessageCreate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    thread = await owned_thread(db, thread_id, user.id)
    if settings.AI_PROVIDER != "simulated":
        if not settings.AI_API_KEY:
            raise HTTPException(503, "AI_CONFIGURATION_REQUIRED")
        raise HTTPException(501, "El adaptador real de IA todavía requiere validación del proveedor")
    now = datetime.now(UTC)
    db.add(
        AssistantMessage(
            thread_id=thread.id,
            author="user",
            content=payload.content,
            created_at=now,
            citations=[],
        )
    )
    confirmation = None
    if payload.proposed_write is not None:
        if thread.athlete_scope_id is None:
            raise HTTPException(422, "La conversación necesita un atleta en alcance")
        await require_athlete_access(db, user, thread.athlete_scope_id)
        operation_payload = {
            "athlete_id": thread.athlete_scope_id,
            **payload.proposed_write.payload,
        }
        if payload.proposed_write.operation == "create_complaint":
            if thread.role != "athlete" or user.id != thread.athlete_scope_id:
                raise HTTPException(403, "Sólo el atleta confirma su reporte de molestia")
            ComplaintCreate.model_validate(payload.proposed_write.payload)
        elif payload.proposed_write.operation == "create_workout_draft":
            if thread.role != "coach":
                raise HTTPException(403, "Sólo el entrenador crea borradores")
            WorkoutCreate.model_validate(payload.proposed_write.payload)
        digest = stable_hash(operation_payload)
        confirmation = AssistantConfirmation(
            thread_id=thread.id,
            user_id=user.id,
            operation=payload.proposed_write.operation,
            payload=operation_payload,
            payload_hash=digest,
            expires_at=now + timedelta(minutes=10),
        )
        db.add(confirmation)
        await db.flush()
        response_text = "Preparé una vista previa. Confirma explícitamente para realizar la escritura."
        citations: list[dict] = []
    else:
        facts, citations = await read_facts(db, thread, payload.content)
        draft = SimulatedAssistant().explain(
            role=thread.role,
            question=payload.content,
            facts=facts,
            citations=citations,
        )
        response_text = draft.content
        citations = draft.citations
    assistant_message = AssistantMessage(
        thread_id=thread.id,
        author="assistant",
        content=response_text,
        created_at=now,
        citations=citations,
        provider="simulated",
        model="deterministic-pilot-v1",
        prompt_version="pilot-policy-v1",
    )
    db.add(assistant_message)
    await db.commit()
    return {
        "message": response_text,
        "citations": citations,
        "confirmation": (
            {
                "id": confirmation.id,
                "operation": confirmation.operation,
                "payload": confirmation.payload,
                "payload_hash": confirmation.payload_hash,
                "expires_at": confirmation.expires_at,
            }
            if confirmation
            else None
        ),
    }


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
    if confirmation.payload_hash != payload.payload_hash:
        raise HTTPException(409, "La vista previa cambió; vuelve a generarla")
    if confirmation.consumed_at is not None:
        return confirmation.result
    if utc_aware(confirmation.expires_at) < datetime.now(UTC):
        raise HTTPException(410, "La confirmación expiró")
    athlete_id = int(confirmation.payload["athlete_id"])
    await require_athlete_access(db, user, athlete_id)
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
    await owned_thread(db, thread_id, user.id)
    rows = await db.scalars(
        select(AssistantMessage)
        .where(AssistantMessage.thread_id == thread_id)
        .order_by(AssistantMessage.created_at, AssistantMessage.id)
    )
    return [
        {
            "id": item.id,
            "author": item.author,
            "content": item.content,
            "citations": item.citations,
            "created_at": item.created_at,
        }
        for item in rows.all()
    ]
