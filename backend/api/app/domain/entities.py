from datetime import datetime
from typing import Optional, List
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
    coach_id: Optional[int] = None

# Actividad e Ingesta
class ActivitySummary(BaseEntity):
    id: Optional[int] = None
    athlete_id: int
    file_name: str
    start_time: datetime

    # Resumen general
    total_duration_sec: float = 0.0
    total_distance_m: float = 0.0

    # Cargas
    trimp: Optional[float] = None
    tss: Optional[float] = None

    # Estado del atleta tras la sesión
    ctl: Optional[float] = None
    atl: Optional[float] = None
    tsb: Optional[float] = None
    acwr: Optional[float] = None

class TelemetryPoint(BaseEntity):
    timestamp: datetime
    heart_rate: Optional[int] = None
    speed_ms: Optional[float] = None
    cadence: Optional[int] = None
    altitude: Optional[float] = None
    power: Optional[int] = None
    temperature: Optional[int] = None

class ActivityData(BaseEntity):
    """Agregado que representa la actividad completa con su telemetría"""
    summary: ActivitySummary
    telemetry: List[TelemetryPoint]
