from datetime import date, datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AwareDatetime, BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

Name = Annotated[str, Field(min_length=1, max_length=100)]
Password = Annotated[str, Field(min_length=12, max_length=128)]
Token = Annotated[str, Field(min_length=20, max_length=256)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class Identity(Contract):
    email: EmailStr
    first_name: Name
    last_name: Name
    timezone: str = "UTC"

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        return str(value).lower()

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Zona horaria IANA inválida")
        return value

    @field_validator("first_name", "last_name")
    @classmethod
    def valid_name(cls, value):
        if not value.strip():
            raise ValueError("El nombre no puede estar vacío")
        return value.strip()


class CoachRegistration(Identity):
    password: Password


class UserView(Identity):
    id: int
    role: str
    coach_id: int | None
    is_superuser: bool


class Login(Contract):
    email: EmailStr
    password: Annotated[str, Field(min_length=1, max_length=128)]


class RefreshRequest(Contract):
    refresh_token: Token


class ActivateAthlete(Contract):
    invitation_token: Token
    password: Password


class TokenPair(Contract):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"]
    expires_in: int


class AthleteCreated(Contract):
    athlete: UserView
    invitation_token: str
    invitation_expires_at: datetime


class BlockCreate(Contract):
    title: Annotated[str, Field(min_length=1, max_length=255)]
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def date_order(self):
        if self.end_date < self.start_date:
            raise ValueError("El fin del bloque debe ser igual o posterior al inicio")
        return self


class BlockView(BlockCreate):
    id: int
    athlete_id: int
    coach_id: int


class StepTarget(Contract):
    metric: Literal["pace", "power", "heart_rate", "rpe"]
    unit: Literal["sec_per_km", "sec_per_100m", "watts", "bpm", "rpe_0_10"]
    minimum: float = Field(gt=0, allow_inf_nan=False)
    maximum: float = Field(gt=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def valid_target(self):
        units = {"pace": {"sec_per_km", "sec_per_100m"}, "power": {"watts"},
                 "heart_rate": {"bpm"}, "rpe": {"rpe_0_10"}}
        if self.unit not in units[self.metric] or self.minimum > self.maximum:
            raise ValueError("Objetivo o unidad incompatible")
        if self.metric == "rpe" and self.maximum > 10:
            raise ValueError("RPE debe estar entre 0 y 10")
        return self


class WorkoutStep(Contract):
    kind: Literal["warmup", "work", "recovery", "cooldown"]
    duration_sec: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    distance_m: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    target: StepTarget | None = None

    @model_validator(mode="after")
    def one_measure(self):
        if (self.duration_sec is None) == (self.distance_m is None):
            raise ValueError("Cada paso requiere duración o distancia, exactamente una")
        return self


class StepGroup(Contract):
    repetitions: int = Field(default=1, ge=1, le=100)
    steps: list[WorkoutStep] = Field(min_length=1, max_length=20)


class WorkoutCreate(Contract):
    title: Annotated[str, Field(min_length=1, max_length=255)]
    description: str | None = Field(default=None, max_length=4000)
    scheduled_date: AwareDatetime
    sport_type: Literal["running", "cycling", "swimming"]
    block_id: int | None = Field(default=None, gt=0)
    steps: list[StepGroup] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def valid_sport_targets(self):
        for group in self.steps:
            for step in group.steps:
                if not step.target:
                    continue
                if step.target.unit == "sec_per_100m" and self.sport_type != "swimming":
                    raise ValueError("Ritmo por 100 m reservado para natación")
                if step.target.unit == "sec_per_km" and self.sport_type != "running":
                    raise ValueError("Ritmo por km reservado para carrera")
        return self


class WorkoutReplace(WorkoutCreate):
    expected_version: int = Field(ge=1)


class PublishWorkout(Contract):
    expected_version: int = Field(ge=1)


class WorkoutView(WorkoutCreate):
    scheduled_date: datetime
    id: int
    athlete_id: int
    coach_id: int | None
    status: str
    version: int
