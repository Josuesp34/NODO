from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

Purpose = Literal["training_data_processing", "ai_assistant", "web_push"]
Category = Literal["plan", "reminder", "review", "sync"]


class PrivateContract(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class PreferencesUpdate(PrivateContract):
    enabled: bool = False
    categories: list[Category] = Field(default_factory=list, max_length=4)
    timezone: str = "UTC"
    quiet_start: str | None = Field(default=None, pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")
    quiet_end: str | None = Field(default=None, pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except (ValueError, ZoneInfoNotFoundError) as exc:
            raise ValueError("Zona horaria inválida") from exc
        return value

    @model_validator(mode="after")
    def coherent(self):
        if (self.quiet_start is None) != (self.quiet_end is None):
            raise ValueError("El horario silencioso necesita inicio y fin")
        if len(set(self.categories)) != len(self.categories):
            raise ValueError("No repetir categorías")
        return self


class PushKeys(PrivateContract):
    p256dh: str = Field(min_length=80, max_length=128)
    auth: str = Field(min_length=20, max_length=32)


class PushRegistration(PrivateContract):
    endpoint: str = Field(min_length=10, max_length=4096)
    keys: PushKeys
    expirationTime: int | None = Field(default=None, gt=0, le=253402300799000)


class PushSubscriptionView(PrivateContract):
    id: int
    endpoint_hash: str
    created_at: datetime
    revoked_at: datetime | None
    expires_at: datetime | None


class PurposeGrant(PrivateContract):
    scope: Purpose
    version: Literal["pilot-v1"]


class OrganizationStatus(PrivateContract):
    status: Literal["active", "suspended"]
    reason: str = Field(min_length=1, max_length=500)


class SubscriptionStatus(PrivateContract):
    status: Literal["active", "suspended", "cancelled"]
    reason: str = Field(min_length=1, max_length=500)


class RetentionRequest(PrivateContract):
    confirmation: Literal["EJECUTAR RETENCION"]
    before: AwareDatetime | None = None
