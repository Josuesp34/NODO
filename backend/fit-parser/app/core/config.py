from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = "NODO"
    ENVIRONMENT: str = "development"
    API_V1_STR: str = "/api/v1"
    DATABASE_URL: str
    MAX_FIT_BYTES: int = Field(default=10 * 1024 * 1024, gt=0)
    ACCESS_TOKEN_MINUTES: int = Field(default=30, ge=1)
    REFRESH_TOKEN_DAYS: int = Field(default=30, ge=1)
    ALLOW_COACH_REGISTRATION: bool = False


settings = Settings()
