"""
Application Settings
====================
Equivalent to Laravel's config/ directory + .env loading.

All settings are loaded from environment variables (via .env file).
Access settings anywhere with: from app.core.config import get_settings
"""

from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────────────────────
    APP_NAME: str = "AI Product Intelligence Platform"
    APP_ENV: str = "local"
    APP_DEBUG: bool = True
    APP_VERSION: str = "1.0.0"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # ── CORS ──────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: str = (
        "http://localhost:3000,"
        "http://localhost:8003,"
        "http://127.0.0.1:8003"
    )

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_origins(cls, v: str) -> str:
        return v

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = "mysql+aiomysql://root:password@localhost:3306/qumta_db"
    DATABASE_URL_SYNC: str = "mysql+pymysql://root:password@localhost:3306/qumta_db"

    # ── Scraper Database ───────────────────────────────────────────────────────
    SCRAPER_DATABASE_URL: str = "mysql+aiomysql://root:password@localhost:3306/scraper_db"
    SCRAPER_DATABASE_URL_SYNC: str = "mysql+pymysql://root:password@localhost:3306/scraper_db"

    # ── Scraper Sync API ───────────────────────────────────────────────────────
    SCRAPER_SYNC_API_URL: str = "https://api.example.com/v1/products/import"
    SCRAPER_SYNC_API_KEY: str = ""
    SCRAPER_SYNC_BATCH_SIZE: int = 100

    # ── JWT Authentication ────────────────────────────────────────────────────
    SECRET_KEY: str = "change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    ENABLE_TOKEN_BLACKLIST: bool = True

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # ── File Storage ──────────────────────────────────────────────────────────
    STORAGE_DRIVER: str = "local"          # "local" | "s3"
    STORAGE_LOCAL_PATH: str = "storage/uploads"

    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_DEFAULT_REGION: str = "us-east-1"
    AWS_S3_BUCKET: str = "qumta-uploads"
    AWS_S3_ENDPOINT_URL: str = ""

    # ── Embeddings ────────────────────────────────────────────────────────────
    EMBEDDING_DIMENSIONS: int = 1536

    # ── AI / LLM ──────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = "sk-placeholder"
    OPENAI_MODEL: str = "gpt-4o-mini"

    # ── Universal Extraction Pipeline ────────────────────────────────────────
    # Files larger than this (bytes) are routed to the async Celery path
    EXTRACTION_SYNC_MAX_BYTES: int = 2_097_152   # 2 MB
    LLM_CONFIDENCE_THRESHOLD: float = 0.65
    TESSERACT_LANG: str = "eng+ara"

    # ── Convenience ───────────────────────────────────────────────────────────
    @property
    def is_local(self) -> bool:
        return self.APP_ENV == "local"

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


@lru_cache
def get_settings() -> Settings:
    """
    Returns a cached Settings instance.
    Using @lru_cache means the .env file is only read once per process,
    equivalent to Laravel's config caching.
    """
    return Settings()
