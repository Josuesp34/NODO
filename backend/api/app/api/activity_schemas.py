from pydantic import BaseModel, ConfigDict, Field


class ActivityLink(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prescribed_workout_id: int | None = Field(default=None, gt=0)
    expected_version: int = Field(ge=1)
