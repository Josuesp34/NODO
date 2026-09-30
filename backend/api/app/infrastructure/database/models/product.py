from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin

JSON_VALUE = JSON().with_variant(JSONB(), "postgresql")


class UserRoleAssignment(Base, TimestampMixin):
    __tablename__ = "user_roles"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    __table_args__ = (UniqueConstraint("user_id", "role", name="uq_user_role"),)


class AuthRateLimit(Base, TimestampMixin):
    __tablename__ = "auth_rate_limits"
    id: Mapped[int] = mapped_column(primary_key=True)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    failures: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    blocked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="active", server_default="active")


class OrganizationMembership(Base, TimestampMixin):
    __tablename__ = "organization_memberships"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="active", server_default="active")
    __table_args__ = (UniqueConstraint("organization_id", "user_id", name="uq_organization_member"),)


class CoachAthleteAssignment(Base, TimestampMixin):
    __tablename__ = "coach_athlete_assignments"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    coach_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="active", server_default="active")
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (UniqueConstraint("coach_id", "athlete_id", name="uq_coach_athlete"),)


class AthleteProfile(Base, TimestampMixin):
    __tablename__ = "athlete_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    sports: Mapped[list] = mapped_column(JSON_VALUE, default=list)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    goals: Mapped[dict] = mapped_column(JSON_VALUE, default=dict)
    availability: Mapped[dict] = mapped_column(JSON_VALUE, default=dict)
    rest_hr: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_hr: Mapped[float | None] = mapped_column(Float, nullable=True)
    ftp: Mapped[float | None] = mapped_column(Float, nullable=True)
    threshold_pace_sec_per_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    trimp_variant: Mapped[str | None] = mapped_column(String(30), nullable=True)
    source: Mapped[str] = mapped_column(String(80), nullable=False, default="manual", server_default="manual")
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    __table_args__ = (
        UniqueConstraint("athlete_id", "valid_from", name="uq_athlete_profile_version"),
        CheckConstraint("max_hr IS NULL OR rest_hr IS NULL OR max_hr > rest_hr", name="ck_profile_hr_range"),
    )


class Competition(Base, TimestampMixin):
    __tablename__ = "competitions"
    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    athlete_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    coach_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    competition_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    discipline: Mapped[str] = mapped_column(String(40), nullable=False)
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default="B", server_default="B")


class ActivityLap(Base):
    __tablename__ = "activity_laps"
    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id", ondelete="CASCADE"), index=True)
    lap_index: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_heart_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_power: Mapped[int | None] = mapped_column(Integer, nullable=True)
    __table_args__ = (UniqueConstraint("activity_id", "lap_index", name="uq_activity_lap"),)


class DailyLoad(Base, TimestampMixin):
    __tablename__ = "daily_load"
    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    local_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    load_unit: Mapped[str] = mapped_column(String(20), nullable=False)
    load_value: Mapped[float] = mapped_column(Float, nullable=False)
    ctl: Mapped[float] = mapped_column(Float, nullable=False)
    atl: Mapped[float] = mapped_column(Float, nullable=False)
    tsb: Mapped[float] = mapped_column(Float, nullable=False)
    formula_version: Mapped[str] = mapped_column(String(40), nullable=False)
    recomputed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (UniqueConstraint("athlete_id", "local_date", "load_unit", name="uq_daily_load"),)


class Observation(Base, TimestampMixin):
    __tablename__ = "observations"
    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    metric_type: Mapped[str] = mapped_column(String(60), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    method: Mapped[str] = mapped_column(String(80), nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    device_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    observed_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    observed_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quality: Mapped[str] = mapped_column(String(30), nullable=False)
    __table_args__ = (
        UniqueConstraint("athlete_id", "source", "external_id", "observed_start", name="uq_observation_external"),
        Index("ix_observations_time_brin", "observed_start", postgresql_using="brin"),
    )


class Checkin(Base, TimestampMixin):
    __tablename__ = "checkins"
    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    local_date: Mapped[date] = mapped_column(Date, nullable=False)
    fatigue: Mapped[int | None] = mapped_column(Integer, nullable=True)
    perceived_rest: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stress: Mapped[int | None] = mapped_column(Integer, nullable=True)
    session_rpe: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    __table_args__ = (UniqueConstraint("athlete_id", "local_date", name="uq_checkin_date"),)


class Complaint(Base, TimestampMixin):
    __tablename__ = "complaints"
    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    athlete_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    zone: Mapped[str] = mapped_column(String(120), nullable=False)
    laterality: Mapped[str] = mapped_column(String(20), nullable=False)
    intensity_0_10: Mapped[int] = mapped_column(Integer, nullable=False)
    started_on: Mapped[date] = mapped_column(Date, nullable=False)
    limits_movement: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="reported", server_default="reported")
    __table_args__ = (CheckConstraint("intensity_0_10 BETWEEN 0 AND 10", name="ck_complaint_intensity"),)


class ComplaintUpdate(Base, TimestampMixin):
    __tablename__ = "complaint_updates"
    id: Mapped[int] = mapped_column(primary_key=True)
    complaint_id: Mapped[int] = mapped_column(ForeignKey("complaints.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    intensity_0_10: Mapped[int] = mapped_column(Integer, nullable=False)
    limits_movement: Mapped[bool] = mapped_column(Boolean, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    __table_args__ = (CheckConstraint("intensity_0_10 BETWEEN 0 AND 10", name="ck_complaint_update_intensity"),)


class ReviewItem(Base, TimestampMixin):
    __tablename__ = "review_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    athlete_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    complaint_id: Mapped[int | None] = mapped_column(ForeignKey("complaints.id", ondelete="CASCADE"), nullable=True)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="open", server_default="open")
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class AthleteGroup(Base, TimestampMixin):
    __tablename__ = "athlete_groups"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    coach_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)


class GroupMembership(Base, TimestampMixin):
    __tablename__ = "group_memberships"
    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    group_id: Mapped[int] = mapped_column(ForeignKey("athlete_groups.id", ondelete="CASCADE"), index=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    overrides: Mapped[dict] = mapped_column(JSON_VALUE, default=dict)
    __table_args__ = (UniqueConstraint("group_id", "athlete_id", name="uq_group_athlete"),)


class PlanTemplate(Base, TimestampMixin):
    __tablename__ = "plan_templates"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    coach_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sport_type: Mapped[str] = mapped_column(String(40), nullable=False)
    workouts: Mapped[list] = mapped_column(JSON_VALUE, default=list)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class PlanAssignment(Base, TimestampMixin):
    workout_refs: Mapped[dict] = mapped_column(JSON_VALUE, default=dict, server_default="{}")
    __tablename__ = "plan_assignments"
    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("plan_templates.id", ondelete="CASCADE"), index=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    overrides: Mapped[dict] = mapped_column(JSON_VALUE, default=dict)
    applied_version: Mapped[int] = mapped_column(Integer, nullable=False)
    __table_args__ = (UniqueConstraint("template_id", "athlete_id", name="uq_template_athlete"),)


class IngestionEvent(Base, TimestampMixin):
    __tablename__ = "ingestion_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="received", server_default="received")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    __table_args__ = (UniqueConstraint("provider", "external_id", name="uq_ingestion_external"),)


class Job(Base, TimestampMixin):
    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON_VALUE, nullable=False)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, default=5, server_default="5")
    locked_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", server_default="pending", index=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    dedupe_key: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)


class AthleteConnection(Base, TimestampMixin):
    __tablename__ = "athlete_connections"
    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    external_athlete_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    access_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    scopes: Mapped[list] = mapped_column(JSON_VALUE, default=list)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (UniqueConstraint("athlete_id", "provider", name="uq_athlete_provider"),)


class Consent(Base, TimestampMixin):
    __tablename__ = "consents"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    scope: Mapped[str] = mapped_column(String(80), nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (UniqueConstraint("user_id", "scope", "version", name="uq_consent_version"),)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    entity: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(80), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    before: Mapped[dict | None] = mapped_column(JSON_VALUE, nullable=True)
    after: Mapped[dict | None] = mapped_column(JSON_VALUE, nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class AssistantThread(Base, TimestampMixin):
    __tablename__ = "assistant_threads"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    athlete_scope_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)


class AssistantMessage(Base):
    __tablename__ = "assistant_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("assistant_threads.id", ondelete="CASCADE"), index=True)
    author: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    citations: Mapped[list] = mapped_column(JSON_VALUE, default=list)
    provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(40), nullable=True)


class AssistantConfirmation(Base, TimestampMixin):
    __tablename__ = "assistant_confirmations"
    id: Mapped[int] = mapped_column(primary_key=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("assistant_threads.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    operation: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON_VALUE, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON_VALUE, nullable=True)


class Recommendation(Base, TimestampMixin):
    __tablename__ = "recommendations"
    id: Mapped[int] = mapped_column(primary_key=True)
    coach_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    workout_id: Mapped[int] = mapped_column(ForeignKey("prescribed_workouts.id", ondelete="CASCADE"), index=True)
    base_plan_version: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence: Mapped[list] = mapped_column(JSON_VALUE, default=list)
    changes: Mapped[dict] = mapped_column(JSON_VALUE, nullable=False)
    rules_version: Mapped[str] = mapped_column(String(40), nullable=False)
    model_version: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending", server_default="pending")


class Decision(Base, TimestampMixin):
    __tablename__ = "decisions"
    __table_args__ = (UniqueConstraint("recommendation_id", name="uq_decision_recommendation"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    recommendation_id: Mapped[int] = mapped_column(ForeignKey("recommendations.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CommercialPlan(Base, TimestampMixin):
    __tablename__ = "commercial_plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    athlete_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    monthly_price_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    __table_args__ = (CheckConstraint("athlete_limit > 0", name="ck_plan_athlete_limit"),)


class Subscription(Base, TimestampMixin):
    __tablename__ = "subscriptions"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), unique=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("commercial_plans.id"))
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date | None] = mapped_column(Date, nullable=True)


class ManagedPayment(Base, TimestampMixin):
    __tablename__ = "managed_payments"
    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(ForeignKey("subscriptions.id", ondelete="CASCADE"), index=True)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    paid_on: Mapped[date] = mapped_column(Date, nullable=False)
    reference: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    recorded_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    __table_args__ = (CheckConstraint("amount_cents >= 0", name="ck_payment_amount"),)
