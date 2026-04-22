"""
Core configuration - loaded from environment variables / .env file.
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    APP_TITLE: str = "Corporate Platform"
    APP_DESCRIPTION: str = "Internal webapp platform"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production-use-a-long-random-string"

    # ── Server ───────────────────────────────────────────────────────────────
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    WORKERS: int = 1

    # ── Database ─────────────────────────────────────────────────────────────
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "corporate_platform"
    DB_USER: str = "platform_user"
    DB_PASSWORD: str = "changeme"
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_ECHO: bool = False

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    # ── Auth / Session ────────────────────────────────────────────────────────
    # Users file (JSON, replaces .htpasswd — managed via scripts/manage_users.py)
    USERS_FILE: str = ".users.json"

    # Legacy: keep for backward compat / migration period
    HTPASSWD_FILE: str = ".htpasswd"

    # Session cookie lifetime in seconds (default: 8 hours)
    SESSION_MAX_AGE: int = 28800

    # Cookie security — set True when behind HTTPS
    SESSION_COOKIE_SECURE: bool = False
    SESSION_COOKIE_SAMESITE: str = "lax"

    # Paths that never require authentication
    PUBLIC_PATHS: List[str] = [
        "/health",
        "/static",
        "/login",
        "/favicon.ico",
    ]

    # ── Logging ──────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = ""
    LOG_FORMAT: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    # ── Templates ────────────────────────────────────────────────────────────
    TEMPLATES_DIR: str = "templates"
    STATIC_DIR: str = "static"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
