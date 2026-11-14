"""Shared application settings.

Values can be overridden with environment variables or a .env file. No secrets
are required by this application; the JPL Horizons API is public.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Lunar Navigator API"
    app_version: str = "1.0.0"
    environment: str = "development"

    data_dir: Path = BACKEND_DIR / "data"
    cache_dir: Path = BACKEND_DIR / "data" / "cache"

    #: Allow browser clients from the Vite dev server / built preview.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173"

    #: JPL Horizons live cross-check (optional, public endpoint).
    horizons_enabled: bool = True
    horizons_url: str = "https://ssd.jpl.nasa.gov/api/horizons.api"
    horizons_timeout_seconds: float = 20.0
    horizons_cache_ttl_seconds: int = 86400

    #: Maximum timeline samples per request.
    max_timeline_samples: int = 5000
    #: Default analysis window.
    default_window_days: float = 7.0
    default_step_minutes: int = 10

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
