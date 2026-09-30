from dataclasses import dataclass


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
