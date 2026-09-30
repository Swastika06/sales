from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    APP_NAME: str = "TCG Partner Portal API"
    APP_ENV: Literal["development", "test", "production"] = "development"
    APP_DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: str = "http://localhost:5173"

    DATABASE_URL: str = (
        "postgresql+asyncpg://partner_portal:partner_portal@localhost:5432/partner_portal"
    )

    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_SECURE: bool = False
    MINIO_BUCKET: str = "partner-portal"

    PUBLIC_PORTAL_URL: str = "http://localhost:5173"
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "partners@tcgdigital.com"
    SMTP_STARTTLS: bool = True
    SMTP_SSL: bool = False
    CLAMAV_HOST: str = ""
    CLAMAV_PORT: int = 3310

    JWT_SECRET_KEY: str = Field(
        default="change-me-to-a-long-random-secret-before-use", min_length=32
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, ge=1, le=1440)

    SEED_ADMIN_EMAIL: str = "admin@tcgdigital.com"
    SEED_ADMIN_PASSWORD: str = Field(default="ChangeMe123!", min_length=12)
    SEED_ADMIN_NAME: str = "TCG Administrator"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    def assert_safe_for_production(self) -> None:
        if self.APP_ENV == "production":
            if self.JWT_SECRET_KEY.startswith("change-me"):
                raise ValueError("JWT_SECRET_KEY must be replaced in production")
            if not self.PUBLIC_PORTAL_URL.startswith("https://"):
                raise ValueError("PUBLIC_PORTAL_URL must use HTTPS in production")
            if not self.SMTP_HOST or not (self.SMTP_STARTTLS or self.SMTP_SSL):
                raise ValueError("Configure an SMTP host with TLS for production onboarding")
            if not self.CLAMAV_HOST:
                raise ValueError("Configure CLAMAV_HOST for production document scanning")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.assert_safe_for_production()
    return settings


settings = get_settings()
