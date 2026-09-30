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
    WORKER_POLL_INTERVAL_SECONDS: int = Field(default=5, ge=1)
    WORKER_BATCH_SIZE: int = Field(default=10, ge=1, le=100)
    JOB_MAX_ATTEMPTS: int = Field(default=5, ge=1, le=20)
    JOB_BACKOFF_BASE_SECONDS: int = Field(default=30, ge=1)
    AI_PROVIDER: str = "simulated"
    AI_API_KEY: str = ""
    AI_MODEL: str = ""
    RESEND_API_KEY: str = ""
    RESEND_FROM_EMAIL: str = ""
    EMAIL_QUEUE_KEY: str = ""
    PUBLIC_APP_URL: str = "http://localhost:3000"
    INTERVALS_CLIENT_ID: str = ""
    INTERVALS_CLIENT_SECRET: str = ""
    INTERVALS_REDIRECT_URI: str = ""
    INTERVALS_WEBHOOK_SECRET: str = ""
    PROVIDER_TOKEN_ENCRYPTION_KEY: str = ""
    DATA_RETENTION_DAYS: int = Field(default=365, ge=30)

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
