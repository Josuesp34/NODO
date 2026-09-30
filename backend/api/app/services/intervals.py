from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class NormalizedIntervalsObservation:
    external_id: str
    metric_type: str
    value: float
    unit: str
    method: str
    observed_start: datetime
    observed_end: datetime
    quality: str


class IntervalsAdapter(Protocol):
    provider: str

    async def exchange_authorization_code(self, code: str) -> dict: ...

    async def backfill(self, external_athlete_id: str, days: int) -> list[dict]: ...

    def normalize_observation(self, payload: dict) -> NormalizedIntervalsObservation: ...


class SimulatedIntervalsAdapter:
    provider = "intervals_icu"

    async def exchange_authorization_code(self, code: str) -> dict:
        raise RuntimeError("El simulador no emite credenciales reales")

    async def backfill(self, external_athlete_id: str, days: int) -> list[dict]:
        del external_athlete_id, days
        return []

    def normalize_observation(self, payload: dict) -> NormalizedIntervalsObservation:
        required = {
            "external_id",
            "metric_type",
            "value",
            "unit",
            "method",
            "observed_start",
            "observed_end",
        }
        missing = sorted(required - payload.keys())
        if missing:
            raise ValueError(f"Faltan campos de Intervals: {', '.join(missing)}")
        start = datetime.fromisoformat(str(payload["observed_start"]).replace("Z", "+00:00"))
        end = datetime.fromisoformat(str(payload["observed_end"]).replace("Z", "+00:00"))
        if end < start:
            raise ValueError("El periodo de Intervals es inválido")
        return NormalizedIntervalsObservation(
            external_id=str(payload["external_id"]),
            metric_type=str(payload["metric_type"]),
            value=float(payload["value"]),
            unit=str(payload["unit"]),
            method=str(payload["method"]),
            observed_start=start,
            observed_end=end,
            quality=str(payload.get("quality", "partial")),
        )
