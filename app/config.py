from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    APP_NAME: str = "QSignHub API"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    DEBUG: bool = False
    BASE_URL: str = "http://localhost:8000"

    # Security
    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    API_KEY_PREFIX: str = "qsh_"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://qsignhub:qsignhub@localhost:5432/qsignhub"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # Redis (Celery broker + cache)
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # Storage (S3-compatible)
    STORAGE_BACKEND: str = "s3"  # s3 | local
    S3_ENDPOINT_URL: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET_DOCUMENTS: str = "qsignhub-documents"
    S3_BUCKET_SIGNED: str = "qsignhub-signed"
    LOCAL_STORAGE_PATH: str = "/tmp/qsignhub"

    # Signing session
    SIGNING_SESSION_EXPIRE_HOURS: int = 72
    SIGNING_SESSION_BASE_URL: str = "http://localhost:3000"

    # Webhooks
    WEBHOOK_SECRET_HEADER: str = "X-QSignHub-Signature"
    WEBHOOK_TIMEOUT_SECONDS: int = 30
    WEBHOOK_MAX_RETRIES: int = 5

    # Email notifications
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@qsignhub.com"
    SMTP_TLS: bool = True

    # eIDAS / HSM
    HSM_ENABLED: bool = False
    HSM_PKCS11_LIB: str = "/usr/lib/softhsm/libsofthsm2.so"
    HSM_SLOT_ID: int = 0
    HSM_PIN: str = ""

    # Trust Service Provider (TSP) integration
    TSP_PROVIDER: str = "demo"  # demo | certum | asseco | kir
    TSP_API_URL: str = ""
    TSP_API_KEY: str = ""

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8080"]

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_BURST: int = 20


@lru_cache
def get_settings() -> Settings:
    return Settings()
