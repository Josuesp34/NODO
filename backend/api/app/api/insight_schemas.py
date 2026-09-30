from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class InitialLoadState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ctl: float = Field(ge=0, le=100000, allow_inf_nan=False)
    atl: float = Field(ge=0, le=100000, allow_inf_nan=False)
    explanation: str = Field(min_length=3, max_length=500)


class LoadAlternative(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=60)
    daily_loads: list[float] = Field(min_length=1, max_length=42)


class CompetitionScenarios(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_competition_version: int = Field(ge=1)
    start_date: date
    load_unit: Literal["trimp", "tss"]
    initial_state: InitialLoadState | None = None
    alternatives: list[LoadAlternative] = Field(min_length=2, max_length=4)
