from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.api.schemas import StepGroup


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())


class ProfileUpsert(Contract):
    sports: list[Literal["running", "cycling", "swimming", "triathlon"]] = Field(min_length=1)
    timezone: str
    goals: dict = Field(default_factory=dict)
    availability: dict = Field(default_factory=dict)
    rest_hr: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    max_hr: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    ftp: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    threshold_pace_sec_per_km: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    trimp_variant: Literal["banister_male", "banister_female"] | None = None
    source: str = Field(default="manual", min_length=1, max_length=80)
    valid_from: date

    @field_validator("timezone")
    @classmethod
    def timezone_exists(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Zona horaria IANA inválida") from None
        return value

    @model_validator(mode="after")
    def valid_hr(self):
        if self.rest_hr is not None and self.max_hr is not None and self.max_hr <= self.rest_hr:
            raise ValueError("La FC máxima debe ser mayor que la FC de reposo")
        return self


class ProfileView(ProfileUpsert):
    id: int
    athlete_id: int
    valid_to: date | None


class CompetitionCreate(Contract):
    name: str = Field(min_length=1, max_length=255)
    competition_date: date
    discipline: Literal["running", "cycling", "swimming", "triathlon"]
    priority: Literal["A", "B", "C"] = "B"


class CompetitionView(CompetitionCreate):
    version: int
    id: int
    athlete_id: int
    coach_id: int


class ObservationCreate(Contract):
    metric_type: str = Field(min_length=1, max_length=60)
    value: float = Field(allow_inf_nan=False)
    unit: str = Field(min_length=1, max_length=40)
    method: str = Field(min_length=1, max_length=80)
    source: str = Field(min_length=1, max_length=80)
    device_id: str | None = Field(default=None, max_length=255)
    observed_start: AwareDatetime
    observed_end: AwareDatetime
    timezone: str
    external_id: str | None = Field(default=None, max_length=255)
    quality: Literal["good", "partial", "estimated", "legacy_unknown"]

    @model_validator(mode="after")
    def valid_period(self):
        if self.observed_end < self.observed_start:
            raise ValueError("El periodo observado es inválido")
        return self


class ObservationView(ObservationCreate):
    id: int
    athlete_id: int
    received_at: datetime


class CheckinUpsert(Contract):
    local_date: date
    fatigue: int | None = Field(default=None, ge=0, le=10)
    perceived_rest: int | None = Field(default=None, ge=0, le=10)
    stress: int | None = Field(default=None, ge=0, le=10)
    session_rpe: int | None = Field(default=None, ge=0, le=10)
    notes: str | None = Field(default=None, max_length=2000)


class CheckinView(CheckinUpsert):
    id: int
    athlete_id: int


class ComplaintCreate(Contract):
    zone: str = Field(min_length=1, max_length=120)
    laterality: Literal["left", "right", "bilateral", "center", "not_applicable"]
    intensity_0_10: int = Field(ge=0, le=10)
    started_on: date
    limits_movement: bool = False
    note: str | None = Field(default=None, max_length=2000)


class ComplaintUpdateCreate(Contract):
    expected_version: int | None = Field(default=None, ge=1)
    intensity_0_10: int = Field(ge=0, le=10)
    limits_movement: bool
    note: str | None = Field(default=None, max_length=2000)


class ComplaintView(ComplaintCreate):
    version: int
    id: int
    athlete_id: int
    status: str


class ReviewDecision(Contract):
    expected_version: int | None = Field(default=None, ge=1)
    status: Literal["reviewed", "follow_up", "closed"]
    note: str = Field(min_length=1, max_length=2000)


class ReviewItemView(Contract):
    version: int
    id: int
    athlete_id: int
    complaint_id: int | None
    kind: str
    priority: str
    reason: str
    status: str
    decision_note: str | None


class GroupCreate(Contract):
    name: str = Field(min_length=1, max_length=255)


class GroupView(GroupCreate):
    id: int
    organization_id: int
    coach_id: int


class GroupMemberCreate(Contract):
    athlete_id: int = Field(gt=0)
    overrides: dict = Field(default_factory=dict)


class GroupMemberView(GroupMemberCreate):
    version: int
    id: int
    group_id: int


class TemplateCreate(Contract):
    name: str = Field(min_length=1, max_length=255)
    sport_type: Literal["running", "cycling", "swimming", "triathlon"]
    workouts: list[dict] = Field(min_length=1, max_length=100)


class TemplateView(TemplateCreate):
    id: int
    organization_id: int
    coach_id: int
    version: int


class TemplateReplace(TemplateCreate):
    expected_version: int = Field(ge=1)


class MemberReplace(Contract):
    overrides: dict
    expected_version: int = Field(ge=1)


class CompetitionReplace(CompetitionCreate):
    expected_version: int = Field(ge=1)


class TemplateApply(Contract):
    athlete_ids: list[int] = Field(default_factory=list, max_length=100)
    group_id: int | None = Field(default=None, gt=0)
    expected_version: int | None = Field(default=None, ge=1)
    overrides: dict[int, dict] = Field(default_factory=dict)


class ConsentGrant(Contract):
    scope: str = Field(min_length=1, max_length=80)
    version: str = Field(min_length=1, max_length=40)


class ConsentView(ConsentGrant):
    id: int
    user_id: int
    granted_at: datetime
    revoked_at: datetime | None


class DeleteAccount(Contract):
    password: str = Field(min_length=1, max_length=128)
    confirmation: Literal["ELIMINAR MI CUENTA"]


class ConnectionRequest(Contract):
    mode: Literal["simulated", "real"] = "simulated"


class ConnectionView(Contract):
    provider: str
    status: str
    last_sync_at: datetime | None


class PlanCreate(Contract):
    name: str = Field(min_length=1, max_length=120)
    athlete_limit: int = Field(gt=0, le=10000)
    monthly_price_cents: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)

    @model_validator(mode="after")
    def price_and_currency(self):
        if (self.monthly_price_cents is None) != (self.currency is None):
            raise ValueError("Precio y moneda deben definirse juntos")
        return self


class SubscriptionCreate(Contract):
    organization_id: int = Field(gt=0)
    plan_id: int = Field(gt=0)
    starts_on: date
    ends_on: date | None = None


class PaymentCreate(Contract):
    subscription_id: int = Field(gt=0)
    amount_cents: int = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)
    paid_on: date
    reference: str = Field(min_length=1, max_length=255)


class WorkoutChanges(Contract):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    scheduled_date: AwareDatetime | None = None
    sport_type: Literal["running", "cycling", "swimming", "triathlon"] | None = None
    block_id: int | None = Field(default=None, gt=0)
    steps: list[StepGroup] | None = Field(default=None, min_length=1, max_length=50)

    @model_validator(mode="after")
    def not_empty(self):
        if not self.model_dump(exclude_none=True):
            raise ValueError("La propuesta no contiene cambios")
        return self


class RecommendationCreate(Contract):
    athlete_id: int = Field(gt=0)
    workout_id: int = Field(gt=0)
    evidence: list[dict] = Field(default_factory=list)
    changes: WorkoutChanges


class RecommendationDecision(Contract):
    action: Literal["approve", "modify", "reject"]
    changes: WorkoutChanges | None = None
    expected_plan_version: int | None = Field(default=None, ge=1)
    note: str | None = Field(default=None, max_length=2000)


class RecommendationView(Contract):
    id: int
    coach_id: int
    athlete_id: int
    workout_id: int
    base_plan_version: int
    evidence: list[dict]
    changes: dict
    rules_version: str
    model_version: str
    status: str
    created_at: datetime
    updated_at: datetime
