"""Provider state contains no plaintext credentials; budgets use integer micro-USD."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin
from .product import JSON_VALUE, AthleteConnection


class ProviderOAuthState(Base):
    __tablename__ = "provider_oauth_states"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("auth_sessions.id", ondelete="CASCADE"))
    state_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProviderRecord(Base, TimestampMixin):
    __tablename__ = "provider_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(40))
    external_id: Mapped[str] = mapped_column(String(255))
    payload: Mapped[dict] = mapped_column(JSON_VALUE)
    __table_args__ = (UniqueConstraint("athlete_id", "provider", "kind", "external_id", name="uq_provider_record"),)


class AssistantRun(Base, TimestampMixin):
    __tablename__ = "assistant_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("assistant_threads.id", ondelete="CASCADE"), index=True)
    request_key: Mapped[str] = mapped_column(String(80))
    request_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(30), default="running")
    result: Mapped[dict | None] = mapped_column(JSON_VALUE, nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_microusd: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    __table_args__ = (UniqueConstraint("thread_id", "request_key", name="uq_assistant_run_request"),)


class AssistantBudget(Base):
    __tablename__ = "assistant_budgets"
    id: Mapped[int] = mapped_column(primary_key=True)
    scope: Mapped[str] = mapped_column(String(20))
    scope_id: Mapped[int] = mapped_column(Integer)
    month: Mapped[date] = mapped_column(Date)
    requests: Mapped[int] = mapped_column(Integer, default=0)
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_microusd: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (UniqueConstraint("scope", "scope_id", "month", name="uq_assistant_budget_month"),)


# Enforce remote identity uniqueness even when two OAuth callbacks race.
Index(
    "uq_active_intervals_external",
    AthleteConnection.provider,
    AthleteConnection.external_athlete_id,
    unique=True,
    postgresql_where=text(
        "status IN ('connected', 'syncing', 'disconnect_pending') AND external_athlete_id IS NOT NULL"
    ),
    sqlite_where=text("status IN ('connected', 'syncing', 'disconnect_pending') AND external_athlete_id IS NOT NULL"),
)
