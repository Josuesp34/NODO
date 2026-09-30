from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import User
from app.infrastructure.database.models.product import AssistantMessage, AssistantThread
from app.services.access import has_athlete_access, require_athlete_access, require_role

REDACTED_MESSAGE = "Este mensaje ya no está disponible porque cambió el acceso a sus datos."
PROVENANCE_ONLY = "_context_only"


async def require_assistant_thread_access(db: AsyncSession, user: User, thread: AssistantThread) -> None:
    if thread.owner_id != user.id:
        raise HTTPException(404, "Conversación no encontrada")
    from app.services.provider_policy import require_provider_consent

    await require_provider_consent(db, user.id, "ai_assistant")
    # Provider wait may have ended after platform privileges changed. The consent
    # guard refreshes User under lock before role checks inspect is_superuser.
    await require_role(db, user, thread.role)
    if thread.role == "athlete" and thread.athlete_scope_id != user.id:
        raise HTTPException(404, "Conversación no encontrada")
    if thread.athlete_scope_id is not None:
        await require_athlete_access(db, user, thread.athlete_scope_id)
        await require_provider_consent(db, thread.athlete_scope_id, "training_data_processing")


async def assistant_message_view(db: AsyncSession, user: User, message: AssistantMessage) -> dict:
    content, citations = message.content, message.citations or []
    from app.services.provider_policy import require_provider_consent

    for citation in citations:
        athlete_id = citation.get("athlete_id") if isinstance(citation, dict) else None
        if (
            not isinstance(athlete_id, int)
            or isinstance(athlete_id, bool)
            or not await has_athlete_access(db, user, athlete_id)
        ):
            # Removing only a citation would leave the derived sensitive text exposed.
            content, citations = REDACTED_MESSAGE, []
            break
        try:
            await require_provider_consent(db, athlete_id, "training_data_processing")
        except HTTPException:
            content, citations = REDACTED_MESSAGE, []
            break
    return {
        "id": message.id,
        "author": message.author,
        "content": content,
        "citations": [citation for citation in citations if not citation.get(PROVENANCE_ONLY)],
        "created_at": message.created_at,
    }


@dataclass
class AssistantDraft:
    content: str
    citations: list[dict]


class SimulatedAssistant:
    """Deterministic provider used by tests and local development.

    It never interprets external text as policy and never writes. Routes execute
    typed tools after server-side authorization and explicit confirmation.
    """

    name = "simulated"
    model = "deterministic-pilot-v1"

    def explain(self, *, role: str, question: str, facts: list[str], citations: list[dict]) -> AssistantDraft:
        if not facts:
            return AssistantDraft(
                content="No hay datos suficientes para responder con evidencia. Puedes continuar manualmente.",
                citations=[],
            )
        prefix = "Resumen para el entrenador" if role == "coach" else "Resumen de tus datos"
        return AssistantDraft(content=f"{prefix}: " + " ".join(facts), citations=citations)
