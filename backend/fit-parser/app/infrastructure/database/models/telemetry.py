from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import Float, Integer, DateTime, ForeignKey, Index, PrimaryKeyConstraint, desc
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.infrastructure.database.models.base import Base

if TYPE_CHECKING:
    from app.infrastructure.database.models.activity import Activity

class TelemetryRecord(Base):
    __tablename__ = "telemetry_records"

    # Clave primaria compuesta obligatoria para hypertables de TimescaleDB
    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id", ondelete="CASCADE"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Sensores biométricos y cinemáticos
    heart_rate: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    speed_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cadence: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    altitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    power: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    temperature: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("activity_id", "timestamp"),
        Index("telemetry_records_timestamp_idx", desc("timestamp")),
    )

    activity: Mapped["Activity"] = relationship("Activity", back_populates="telemetry_records")
