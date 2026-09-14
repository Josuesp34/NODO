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
    ALLOW_SUPERUSER_BOOTSTRAP: bool = False
    DEV_SUPERUSER_BOOTSTRAP_TOKEN: str = ""
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
