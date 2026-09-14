from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BaseEntity(BaseModel):
    model_config = ConfigDict(from_attributes=True)

# Jerarquía
class User(BaseEntity):
    id: int
    email: str
    first_name: str
    last_name: str
    role: str # 'coach' or 'athlete'
    coach_id: int | None = None

# Actividad e Ingesta
class ActivitySummary(BaseEntity):
    id: int | None = None
    athlete_id: int
    file_name: str
    start_time: datetime

    # Resumen general
    total_duration_sec: float = 0.0
    total_distance_m: float = 0.0

    # Cargas
    trimp: float | None = None
    tss: float | None = None

    # Estado del atleta tras la sesión
    ctl: float | None = None
    atl: float | None = None
    tsb: float | None = None
    acwr: float | None = None

class TelemetryPoint(BaseEntity):
    timestamp: datetime
    heart_rate: int | None = None
    speed_ms: float | None = None
    cadence: int | None = None
    altitude: float | None = None
    power: int | None = None
    temperature: int | None = None

class ActivityData(BaseEntity):
    """Agregado que representa la actividad completa con su telemetría"""
    summary: ActivitySummary
    telemetry: list[TelemetryPoint]
