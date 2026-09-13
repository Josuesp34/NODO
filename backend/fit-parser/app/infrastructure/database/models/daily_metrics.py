from datetime import date
from typing import Optional, TYPE_CHECKING
from sqlalchemy import Float, Integer, Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.infrastructure.database.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.infrastructure.database.models.user import User

class DailyPhysiology(Base, TimestampMixin):
    """Métricas fisiológicas diarias para ajustar la carga de entrenamiento."""
    __tablename__ = "daily_physiology"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date_recorded: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Variabilidad de la Frecuencia Cardíaca y métricas de sueño
    rmssd: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # HRV en ms
    resting_hr: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sleep_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sleep_duration_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Estrés subjetivo (1-10)
    perceived_stress: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint('athlete_id', 'date_recorded', name='uix_athlete_date'),
    )

    athlete: Mapped["User"] = relationship("User")
