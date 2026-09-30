from typing import Literal

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
    AI_GCP_PROJECT: str = ""
    AI_GCP_LOCATION: str = "us-central1"
    AI_TIMEOUT_SECONDS: int = Field(default=45, ge=5, le=180)
    AI_MAX_OUTPUT_TOKENS: int = Field(default=2048, ge=128, le=8192)
    AI_MAX_CONTEXT_BYTES: int = Field(default=60000, ge=4000, le=200000)
    AI_USER_MONTHLY_REQUESTS: int = Field(default=200, ge=1)
    AI_ORG_MONTHLY_REQUESTS: int = Field(default=2000, ge=1)
    AI_USER_MONTHLY_TOKENS: int = Field(default=1000000, ge=1)
    AI_ORG_MONTHLY_TOKENS: int = Field(default=10000000, ge=1)
    AI_USER_MONTHLY_BUDGET_USD: float = Field(default=0, ge=0, allow_inf_nan=False)
    AI_ORG_MONTHLY_BUDGET_USD: float = Field(default=0, ge=0, allow_inf_nan=False)
    # Operator must configure reviewed model/region prices. Zero disables paid calls.
    AI_INPUT_USD_PER_MILLION: float = Field(default=0, ge=0, allow_inf_nan=False)
    AI_OUTPUT_USD_PER_MILLION: float = Field(default=0, ge=0, allow_inf_nan=False)
    RESEND_API_KEY: str = ""
    RESEND_FROM_EMAIL: str = ""
    EMAIL_QUEUE_KEY: str = ""
    PUBLIC_APP_URL: str = "http://localhost:3000"
    INTERVALS_CLIENT_ID: str = ""
    INTERVALS_CLIENT_SECRET: str = ""
    INTERVALS_REDIRECT_URI: str = ""
    INTERVALS_WEBHOOK_SECRET: str = ""
    PROVIDER_TOKEN_ENCRYPTION_KEY: str = ""
    INTERVALS_BACKFILL_DAYS: int = Field(default=90, ge=1, le=365)
    INTERVALS_SYNC_INTERVAL_HOURS: int = Field(default=6, ge=1, le=168)
    INTERVALS_TIMEOUT_SECONDS: int = Field(default=30, ge=5, le=120)
    INTERVALS_PUSH_WORKOUTS: bool = False
    WEB_PUSH_PUBLIC_KEY: str = ""
    WEB_PUSH_PRIVATE_KEY: str = ""
    WEB_PUSH_CONTACT: str = ""
    PUSH_ENCRYPTION_KEY: str = ""
    PUSH_ENDPOINT_HOSTS: str = "fcm.googleapis.com,updates.push.services.mozilla.com,web.push.apple.com"
    WEB_PUSH_TTL_SECONDS: int = Field(default=3600, ge=0, le=86400)
    RETENTION_JOB_INTERVAL_HOURS: int = Field(default=24, ge=1, le=168)
    RETENTION_OUTBOX_DAYS: int = Field(default=7, ge=1, le=90)
    PRIVACY_STORAGE_ROOT: str = ""
    PRIVACY_GCS_BUCKETS: str = ""
    STORAGE_BACKEND: Literal["none", "local", "gcs"] = "none"
    STORAGE_BUCKET: str = ""
    STORAGE_LOCAL_PATH: str = ""
    DATA_RETENTION_DAYS: int = Field(default=365, ge=30)
    EXPORT_RETENTION_DAYS: int = Field(default=30, ge=1, le=365)

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
