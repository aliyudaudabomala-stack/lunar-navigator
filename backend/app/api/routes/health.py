"""Health and capability discovery."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from ...core.config import get_settings
from ...models.schemas import DEFAULT_MISSION_TIME, HealthResponse
from ...scientific.time import isoformat_z
from ...services.data_sources import data_sources_payload
from ...services.terrain_service import dem_info

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse, summary="Service health and capabilities")
def health() -> HealthResponse:
    settings = get_settings()
    dem = dem_info()
    return HealthResponse(
        app=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        terrain_available=dem["available"],
        dem_product=dem["product_id"],
        horizons_enabled=settings.horizons_enabled,
        default_mission_time_utc=isoformat_z(DEFAULT_MISSION_TIME),
        server_time_utc=isoformat_z(datetime.now(tz=timezone.utc)),
    )


@router.get("/", summary="API index")
def index() -> dict:
    return {
        "name": get_settings().app_name,
        "version": get_settings().app_version,
        "docs": "/docs",
        "default_mission_time_utc": isoformat_z(DEFAULT_MISSION_TIME),
        "endpoints": [
            "/api/v1/health",
            "/api/v1/sites",
            "/api/v1/terrain/dem",
            "/api/v1/terrain/basemap.png",
            "/api/v1/terrain/local",
            "/api/v1/terrain/horizon",
            "/api/v1/astronomy/sky",
            "/api/v1/astronomy/series",
            "/api/v1/astronomy/orientation",
            "/api/v1/analysis",
            "/api/v1/compare",
            "/api/v1/reports/pdf",
            "/api/v1/data-sources",
            "/api/v1/horizons/check",
        ],
    }


@router.get("/data-sources", summary="Dataset and model provenance catalogue")
def data_sources() -> dict:
    return data_sources_payload()
