"""Registro completo de modelos para bootstrap y futuras migraciones."""
from app.infrastructure.database.models.base import Base
from app.infrastructure.database.models.user import User
from app.infrastructure.database.models.activity import Activity
from app.infrastructure.database.models.telemetry import TelemetryRecord
from app.infrastructure.database.models.plan import PrescribedWorkout
from app.infrastructure.database.models.daily_metrics import DailyPhysiology
from app.infrastructure.database.models.auth import AuthSession, AthleteInvitation
from app.infrastructure.database.models.block import TrainingBlock
