from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.models.base import Base, TimestampMixin

# Importación condicional para el linter (Pylance)
if TYPE_CHECKING:
    from app.infrastructure.database.models.telemetry import TelemetryRecord
    from app.infrastructure.database.models.user import User


class Activity(Base, TimestampMixin):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    athlete_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="manual_fit", server_default="manual_fit")
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sport_type: Mapped[str] = mapped_column(String(40), nullable=False, default="running", server_default="running")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC", server_default="UTC")
    prescribed_workout_id: Mapped[int | None] = mapped_column(
        ForeignKey("prescribed_workouts.id", ondelete="SET NULL"), nullable=True
    )
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)

    # Resumen de sesión
    total_duration_sec: Mapped[float] = mapped_column(Float, default=0.0)
    total_distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_heart_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_heart_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_speed_mps: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_elevation_gain_m: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Métricas de carga fisiológica e IA
    calculated_trimp: Mapped[float | None] = mapped_column(Float, nullable=True)
    calculated_tss: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Estado de forma post-entrenamiento (Sistemas Acoplados)
    ctl: Mapped[float | None] = mapped_column(Float, nullable=True)
    atl: Mapped[float | None] = mapped_column(Float, nullable=True)
    tsb: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Relaciones (El modelo de User deberá existir en app.infrastructure.database.models.user o similar)
    athlete: Mapped[Optional["User"]] = relationship("User", back_populates="activities")
    telemetry_records: Mapped[list["TelemetryRecord"]] = relationship(
        "TelemetryRecord", back_populates="activity", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("athlete_id", "file_hash", name="uq_activity_athlete_file_hash"),
        UniqueConstraint("provider", "external_id", name="uq_activity_provider_external_id"),
    )
