"""Registro completo de modelos para bootstrap y futuras migraciones."""

from app.infrastructure.database.models.activity import Activity
from app.infrastructure.database.models.auth import AthleteInvitation, AuthSession, PasswordReset
from app.infrastructure.database.models.base import Base
from app.infrastructure.database.models.block import TrainingBlock
from app.infrastructure.database.models.daily_metrics import DailyPhysiology
from app.infrastructure.database.models.plan import PrescribedWorkout
from app.infrastructure.database.models.product import (
    ActivityLap,
    AssistantConfirmation,
    AssistantMessage,
    AssistantThread,
    AthleteConnection,
    AthleteGroup,
    AthleteProfile,
    AuditLog,
    AuthRateLimit,
    Checkin,
    CoachAthleteAssignment,
    CommercialPlan,
    Competition,
    Complaint,
    ComplaintUpdate,
    Consent,
    DailyLoad,
    Decision,
    GroupMembership,
    IngestionEvent,
    Job,
    ManagedPayment,
    Observation,
    Organization,
    OrganizationMembership,
    PlanAssignment,
    PlanTemplate,
    Recommendation,
    ReviewItem,
    Subscription,
    UserRoleAssignment,
)
from app.infrastructure.database.models.telemetry import TelemetryRecord
from app.infrastructure.database.models.user import User

# Reexportados a propósito: importar este paquete registra cada modelo en el
# metadata de SQLAlchemy, del que dependen Alembic y el bootstrap local.
__all__ = [
    "Activity",
    "ActivityLap",
    "AssistantConfirmation",
    "AssistantMessage",
    "AssistantThread",
    "AthleteConnection",
    "AthleteGroup",
    "AthleteInvitation",
    "AthleteProfile",
    "AuditLog",
    "AuthRateLimit",
    "AuthSession",
    "Base",
    "Checkin",
    "CoachAthleteAssignment",
    "CommercialPlan",
    "Competition",
    "Complaint",
    "ComplaintUpdate",
    "Consent",
    "DailyLoad",
    "DailyPhysiology",
    "Decision",
    "GroupMembership",
    "IngestionEvent",
    "Job",
    "ManagedPayment",
    "Observation",
    "Organization",
    "OrganizationMembership",
    "PasswordReset",
    "PlanAssignment",
    "PlanTemplate",
    "PrescribedWorkout",
    "Recommendation",
    "ReviewItem",
    "Subscription",
    "TelemetryRecord",
    "TrainingBlock",
    "User",
    "UserRoleAssignment",
]
