import asyncio
import json
import math
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.infrastructure.database.models.product import AssistantConfirmation, AssistantMessage
from app.infrastructure.database.models.providers import AssistantBudget, AssistantRun
from app.services.access import primary_organization_id, require_athlete_access
from app.services.assistant import SimulatedAssistant, assistant_message_view, require_assistant_thread_access
from app.services.assistant_tools import full_context
from app.services.provider_policy import require_provider_consent
from app.services.vertex_assistant import ProviderFailure, VertexAssistant


def stable_hash(value):
    import hashlib

    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def confirmation_view(confirmation):
    return {
        "id": confirmation.id,
        "operation": confirmation.operation,
        "payload": confirmation.payload,
        "payload_hash": confirmation.payload_hash,
        "expires_at": confirmation.expires_at.isoformat(),
    }


async def prepare_confirmation(db, user, thread, proposal):
    from app.api.planning_routes import check_block
    from app.api.product_schemas import ComplaintCreate
    from app.api.schemas import WorkoutCreate

    await require_assistant_thread_access(db, user, thread)
    await require_provider_consent(db, user.id, "ai_assistant")
    aid = thread.athlete_scope_id
    if aid is None:
        raise HTTPException(422, "Selecciona un atleta para la escritura")
    await require_athlete_access(db, user, aid)
    await require_provider_consent(db, aid, "training_data_processing")
    # Server scope always wins; schemas forbid athlete_id/coach_id/status injected by model/client.
    if proposal.operation == "create_complaint":
        if thread.role != "athlete" or user.id != aid:
            raise HTTPException(403, "El atleta registra su propia molestia")
        validated = ComplaintCreate.model_validate(proposal.payload)
    else:
        if thread.role != "coach":
            raise HTTPException(403, "El entrenador crea los borradores")
        validated = WorkoutCreate.model_validate(proposal.payload)
        await check_block(validated.block_id, aid, user.id, validated.scheduled_date, db)
    operation_payload = {**validated.model_dump(mode="json"), "athlete_id": aid}
    confirmation = AssistantConfirmation(
        thread_id=thread.id,
        user_id=user.id,
        operation=proposal.operation,
        payload=operation_payload,
        payload_hash=stable_hash(operation_payload),
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    db.add(confirmation)
    await db.flush()
    return confirmation


async def reserve_budget(db, user, token_reserve: int, cost_reserve: int):
    org = await primary_organization_id(db, user.id)
    month = datetime.now(UTC).date().replace(day=1)
    scopes = [
        (
            "organization",
            org,
            settings.AI_ORG_MONTHLY_REQUESTS,
            settings.AI_ORG_MONTHLY_TOKENS,
            int(settings.AI_ORG_MONTHLY_BUDGET_USD * 1000000),
        ),
        (
            "user",
            user.id,
            settings.AI_USER_MONTHLY_REQUESTS,
            settings.AI_USER_MONTHLY_TOKENS,
            int(settings.AI_USER_MONTHLY_BUDGET_USD * 1000000),
        ),
    ]
    reserved = []
    for scope, identifier, requests, tokens, cost in scopes:
        budget = await db.scalar(
            select(AssistantBudget).where(
                AssistantBudget.scope == scope, AssistantBudget.scope_id == identifier, AssistantBudget.month == month
            )
        )
        if budget is None:
            try:
                async with db.begin_nested():
                    budget = AssistantBudget(
                        scope=scope, scope_id=identifier, month=month, requests=0, tokens=0, cost_microusd=0
                    )
                    db.add(budget)
                    await db.flush()
            except IntegrityError:
                budget = await db.scalar(
                    select(AssistantBudget).where(
                        AssistantBudget.scope == scope,
                        AssistantBudget.scope_id == identifier,
                        AssistantBudget.month == month,
                    )
                )
        result = await db.execute(
            update(AssistantBudget)
            .where(
                AssistantBudget.id == budget.id,
                AssistantBudget.requests < requests,
                AssistantBudget.tokens + token_reserve <= tokens,
                AssistantBudget.cost_microusd + cost_reserve <= cost,
            )
            .values(
                requests=AssistantBudget.requests + 1,
                tokens=AssistantBudget.tokens + token_reserve,
                cost_microusd=AssistantBudget.cost_microusd + cost_reserve,
            )
        )
        if result.rowcount != 1:
            raise HTTPException(429, "AI_QUOTA_EXCEEDED: continúa con las herramientas manuales")
        reserved.append(budget.id)
    return reserved


async def prepare_run(db, user, thread, payload):
    await require_assistant_thread_access(db, user, thread)
    await require_provider_consent(db, user.id, "ai_assistant")
    request_key = payload.request_key or secrets.token_urlsafe(24)
    request_hash = stable_hash(payload.model_dump(mode="json", exclude={"request_key"}))
    # Caller locks the thread for creation. The unique key also guards concurrent workers.
    previous = await db.scalar(
        select(AssistantRun).where(AssistantRun.thread_id == thread.id, AssistantRun.request_key == request_key)
    )
    if previous:
        if previous.request_hash != request_hash:
            raise HTTPException(409, "AI_REQUEST_KEY_CONFLICT")
        if previous.status == "completed":
            return previous, None
        raise HTTPException(409, f"AI_REQUEST_{previous.status.upper()}")
    context, citations = await full_context(db, user, thread)
    history_rows = (
        await db.scalars(
            select(AssistantMessage)
            .where(AssistantMessage.thread_id == thread.id)
            .order_by(AssistantMessage.id.desc())
            .limit(20)
        )
    ).all()
    context["history_truncated"] = len(history_rows) > 20
    history = [await assistant_message_view(db, user, m) for m in reversed(history_rows[:20])]
    raw = json.dumps(
        {"context": context, "history": history, "question": payload.content}, ensure_ascii=False, default=str
    ).encode()
    if len(raw) > settings.AI_MAX_CONTEXT_BYTES:
        raise HTTPException(413, "AI_CONTEXT_TOO_LARGE: selecciona un atleta o consulta herramientas por período")
    if settings.AI_PROVIDER not in {"simulated", "vertex"}:
        raise HTTPException(503, "AI_PROVIDER_NOT_SUPPORTED")
    # Reserve worst-case UTF-8 tokens plus schemas/protocol, not a four-characters estimate.
    token_reserve = len(raw) + 20000 + settings.AI_MAX_OUTPUT_TOKENS
    cost_reserve = 0
    if settings.AI_PROVIDER == "vertex" and payload.proposed_write is None:
        if not all(
            (
                settings.AI_MODEL,
                settings.AI_GCP_PROJECT,
                settings.AI_GCP_LOCATION,
                settings.AI_INPUT_USD_PER_MILLION,
                settings.AI_OUTPUT_USD_PER_MILLION,
                settings.AI_USER_MONTHLY_BUDGET_USD,
                settings.AI_ORG_MONTHLY_BUDGET_USD,
            )
        ):
            raise HTTPException(503, "AI_CONFIGURATION_REQUIRED: continúa manualmente")
        cost_reserve = math.ceil(
            (token_reserve - settings.AI_MAX_OUTPUT_TOKENS) * settings.AI_INPUT_USD_PER_MILLION
            + settings.AI_MAX_OUTPUT_TOKENS * settings.AI_OUTPUT_USD_PER_MILLION
        )
    if settings.AI_PROVIDER == "simulated" or payload.proposed_write:
        token_reserve = 0
    budget_ids = await reserve_budget(db, user, token_reserve, cost_reserve)
    run = AssistantRun(
        user_id=user.id,
        thread_id=thread.id,
        request_key=request_key,
        request_hash=request_hash,
        status="running",
        cost_microusd=cost_reserve,
    )
    db.add(run)
    db.add(
        AssistantMessage(
            thread_id=thread.id, author="user", content=payload.content, citations=[], created_at=datetime.now(UTC)
        )
    )
    await db.commit()
    return run, {
        "context": context,
        "citations": citations,
        "history": history,
        "budget_ids": budget_ids,
        "token_reserve": token_reserve,
        "cost_reserve": cost_reserve,
    }


async def complete_run(db, user, thread, payload, run, prepared):
    run_identifier = run.id
    confirmation = None
    selected = prepared["citations"]
    try:
        if payload.proposed_write:
            proposal = payload.proposed_write
            content = "Revisa el borrador y confirma para guardarlo."
        elif settings.AI_PROVIDER == "simulated":
            # Deterministic offline adapter still reads authorized context, explicit status in response/UI.
            facts = []
            for read in prepared["context"]["reads"]:
                if read["tool"] == "review" and read["data"]:
                    facts.extend(f"Atleta {read['athlete_id']}: {item['reason']}" for item in read["data"])
                elif read["tool"] == "calendar":
                    facts.extend(
                        f"{item['scheduled_date']}: {item['title']} ({item['sport_type']})" for item in read["data"]
                    )
            content = (
                SimulatedAssistant()
                .explain(role=thread.role, question=payload.content, facts=facts, citations=selected)
                .content
            )
            proposal = None
        else:
            task = asyncio.create_task(
                VertexAssistant().generate(prepared["context"], prepared["history"], payload.content)
            )
            try:
                async with asyncio.timeout(settings.AI_TIMEOUT_SECONDS):
                    while not task.done():
                        await asyncio.wait({task}, timeout=0.25)
                        await db.refresh(run)
                        await db.commit()
                        if run.status == "cancelled":
                            task.cancel()
                            raise asyncio.CancelledError()
                    generated = await task
            finally:
                if not task.done():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            available = {c["key"]: c for c in selected}
            if any(key not in available for key in generated.answer.citation_keys):
                raise ProviderFailure("AI_INVALID_CITATIONS")
            if available and not generated.answer.citation_keys:
                raise ProviderFailure("AI_MISSING_CITATIONS")
            selected = [available[key] for key in dict.fromkeys(generated.answer.citation_keys)]
            content, proposal = generated.answer.answer, generated.answer.proposed_write
            if (
                generated.input_tokens + generated.output_tokens > prepared["token_reserve"]
                or generated.output_tokens > settings.AI_MAX_OUTPUT_TOKENS
            ):
                raise ProviderFailure("AI_USAGE_LIMIT_EXCEEDED")
            run.input_tokens, run.output_tokens = generated.input_tokens, generated.output_tokens
            actual_cost = math.ceil(
                generated.input_tokens * settings.AI_INPUT_USD_PER_MILLION
                + generated.output_tokens * settings.AI_OUTPUT_USD_PER_MILLION
            )
            for budget_id in prepared["budget_ids"]:
                await db.execute(
                    update(AssistantBudget)
                    .where(AssistantBudget.id == budget_id)
                    .values(
                        tokens=AssistantBudget.tokens
                        - prepared["token_reserve"]
                        + generated.input_tokens
                        + generated.output_tokens,
                        cost_microusd=AssistantBudget.cost_microusd - prepared["cost_reserve"] + actual_cost,
                    )
                )
            run.cost_microusd = actual_cost
        # Recheck after provider wait and before persisting derived text/proposals.
        await require_assistant_thread_access(db, user, thread)
        await require_provider_consent(db, user.id, "ai_assistant")
        for c in selected:
            await require_athlete_access(db, user, c["athlete_id"])
            await require_provider_consent(db, c["athlete_id"], "training_data_processing")
        await db.refresh(run, with_for_update=True)
        if run.status == "cancelled":
            raise asyncio.CancelledError()
        if proposal:
            confirmation = await prepare_confirmation(db, user, thread, proposal)
        message = AssistantMessage(
            thread_id=thread.id,
            author="assistant",
            content=content,
            citations=selected,
            provider=settings.AI_PROVIDER,
            model=settings.AI_MODEL if settings.AI_PROVIDER == "vertex" else "deterministic-pilot-v1",
            prompt_version="nodo-authorized-context-v2",
            created_at=datetime.now(UTC),
        )
        db.add(message)
        await db.flush()
        result = {
            "message": content,
            "message_id": message.id,
            "citations": selected,
            "confirmation": confirmation_view(confirmation) if confirmation else None,
            "run_id": run.id,
            "provider": settings.AI_PROVIDER,
            "usage": {
                "input_tokens": run.input_tokens,
                "output_tokens": run.output_tokens,
                "estimated_cost_microusd": run.cost_microusd,
            },
        }
        run.status, run.result = "completed", result
        await db.commit()
        return result
    except BaseException as exc:
        await db.rollback()
        fresh = await db.get(AssistantRun, run_identifier)
        if fresh:
            fresh.status = "cancelled" if isinstance(exc, asyncio.CancelledError) else "failed"
            fresh.error_code = exc.code if isinstance(exc, ProviderFailure) else "AI_REQUEST_FAILED"
            await db.commit()
        if isinstance(exc, (ProviderFailure, TimeoutError)):
            raise HTTPException(
                503, f"{getattr(exc, 'code', 'AI_TIMEOUT')}: continúa con las herramientas manuales"
            ) from None
        if isinstance(exc, ValueError):
            raise HTTPException(422, "AI_INVALID_PROPOSAL") from None
        raise
