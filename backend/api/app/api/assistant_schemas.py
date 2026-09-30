from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ThreadCreate(Contract):
    role: Literal["coach", "athlete"]
    athlete_scope_id: int | None = Field(default=None, gt=0)
    title: str = Field(default="Nueva conversación", min_length=1, max_length=255)


class ProposedWrite(Contract):
    operation: Literal["create_complaint", "create_workout_draft"]
    payload: dict


class MessageCreate(Contract):
    content: str = Field(min_length=1, max_length=8000)
    proposed_write: ProposedWrite | None = None
    request_key: str | None = Field(default=None, min_length=8, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")


class ConfirmWrite(Contract):
    payload_hash: str = Field(min_length=64, max_length=64)
