from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.models.base import Base, TimestampMixin

# Importación condicional para el linter (Pylance)
if TYPE_CHECKING:
    from app.infrastructure.database.models.telemetry import TelemetryRecord
    from app.infrastructure.database.models.user import User

class Activity(Base, TimestampMixin):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    # TEMPORAL: nullable=True hasta implementar el sistema de login
    athlete_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)

    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)

    # Resumen de sesión
    total_duration_sec: Mapped[float] = mapped_column(Float, default=0.0)
    total_distance_m: Mapped[float] = mapped_column(Float, default=0.0)
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
    acwr: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Relaciones (El modelo de User deberá existir en app.infrastructure.database.models.user o similar)
    athlete: Mapped[Optional["User"]] = relationship("User", back_populates="activities")
    telemetry_records: Mapped[list["TelemetryRecord"]] = relationship(
            "TelemetryRecord",
            back_populates="activity",
            cascade="all, delete-orphan"
        )
