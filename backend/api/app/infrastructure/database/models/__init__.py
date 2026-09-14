"""Registro completo de modelos para bootstrap y futuras migraciones."""
from app.infrastructure.database.models.activity import Activity
from app.infrastructure.database.models.auth import AthleteInvitation, AuthSession
from app.infrastructure.database.models.base import Base
from app.infrastructure.database.models.block import TrainingBlock
from app.infrastructure.database.models.daily_metrics import DailyPhysiology
from app.infrastructure.database.models.plan import PrescribedWorkout
from app.infrastructure.database.models.telemetry import TelemetryRecord
from app.infrastructure.database.models.user import User

# Reexportados a propósito: importar este paquete registra cada modelo en el
# metadata de SQLAlchemy, del que dependen Alembic y el bootstrap local.
__all__ = [
    "Activity",
    "AthleteInvitation",
    "AuthSession",
    "Base",
    "DailyPhysiology",
    "PrescribedWorkout",
    "TelemetryRecord",
    "TrainingBlock",
    "User",
]
