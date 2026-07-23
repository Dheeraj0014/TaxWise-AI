"""Application settings (§9.1 core). Loaded from environment / .env."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "AI Tax Optimizer (India)"
    environment: str = "dev"

    # SQLite for local/dev; swap DATABASE_URL to Postgres in staging/prod.
    database_url: str = "sqlite:///./taxify.db"

    # Auth — override in every real environment.
    jwt_secret: str = "dev-insecure-change-me"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 7

    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    default_assessment_year: int = 2026


@lru_cache
def get_settings() -> Settings:
    return Settings()
