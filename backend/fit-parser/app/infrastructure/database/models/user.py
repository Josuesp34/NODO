from enum import Enum
from typing import List, TYPE_CHECKING, Optional
from sqlalchemy import String, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.infrastructure.database.models.base import Base, TimestampMixin

# Importación condicional para el linter (Pylance)
if TYPE_CHECKING:
    from app.infrastructure.database.models.activity import Activity

class UserRole(str, Enum):
    COACH = "coach"
    ATHLETE = "athlete"

class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", server_default="UTC")
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole),
        default=UserRole.ATHLETE,
        nullable=False
    )

    # Jerarquía: un atleta puede tener un coach
    coach_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    coach: Mapped[Optional["User"]] = relationship("User", remote_side=[id], backref="athletes")

    # Relación uno a muchos con actividades
    activities: Mapped[List["Activity"]] = relationship(
        "Activity",
        back_populates="athlete",
        cascade="all, delete-orphan"
    )
