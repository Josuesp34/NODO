from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Float, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.infrastructure.database.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.infrastructure.database.models.user import User

class PrescribedWorkout(Base, TimestampMixin):
    """Modelo para representar un entrenamiento planificado por el coach."""
    __tablename__ = "prescribed_workouts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    coach_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    scheduled_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)

    # Objetivos planificados
    target_duration_sec: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    target_tss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    target_trimp: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Tipo de deporte (Natación, Ciclismo, Carrera, etc)
    sport_type: Mapped[str] = mapped_column(String(50), default="running")
    block_id: Mapped[Optional[int]] = mapped_column(ForeignKey("training_blocks.id"), nullable=True)
    steps: Mapped[list] = mapped_column(JSON, default=list, server_default="[]")
    status: Mapped[str] = mapped_column(String(20), default="draft", server_default="draft")
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")

    athlete: Mapped["User"] = relationship("User", foreign_keys=[athlete_id])
    coach: Mapped[Optional["User"]] = relationship("User", foreign_keys=[coach_id])
