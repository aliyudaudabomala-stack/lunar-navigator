"""Terrain DEM, basemap and local analysis endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response

from ...services.analysis_service import local_terrain_window
from ...services.terrain_service import (
    basemap_png,
    dem_info,
    horizon_profile_for,
    terrain_snapshot,
)

router = APIRouter(prefix="/terrain", tags=["terrain"])


@router.get("/dem", summary="DEM provenance and availability")
def dem() -> dict:
    return dem_info()


@router.get(
    "/basemap.png",
    summary="Server-rendered LOLA polar hillshade",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
)
def basemap(size: int = Query(1400, ge=200, le=2400)) -> Response:
    png, meta = basemap_png(size=size)
    return Response(
        content=png,
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=86400",
            "X-Terrain-Source": str(meta.get("source", "unknown")),
            "X-DEM-Product": str(meta.get("product_id", "unknown")),
            "X-DEM-Available": "true" if meta.get("available") else "false",
        },
    )


@router.get("/local", summary="Local elevation grid and terrain metrics")
def local(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-360, le=360),
    span_km: float = Query(40.0, gt=1, le=200),
    size: int = Query(96, ge=16, le=256),
) -> dict:
    window = local_terrain_window(lat, lon % 360.0, span_km=span_km, size=size)
    if not window.get("available"):
        raise HTTPException(status_code=422, detail=window.get("reason", "No terrain available"))
    window["terrain"] = {
        k: v for k, v in terrain_snapshot(lat, lon % 360.0).items() if k != "horizon"
    }
    return window


@router.get("/horizon", summary="Terrain horizon profile at a site")
def horizon(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-360, le=360),
    azimuth_step_deg: float = Query(2.0, gt=0.25, le=15),
    max_range_km: float = Query(30.0, gt=1, le=60),
) -> dict:
    profile = horizon_profile_for(
        lat, lon % 360.0, az_step=azimuth_step_deg, max_range_km=max_range_km
    )
    terrain = terrain_snapshot(lat, lon % 360.0)
    return {
        "site": {"lat": lat, "lon": lon % 360.0},
        "terrain": {k: v for k, v in terrain.items() if k != "horizon"},
        "horizon": profile,
        "method": (
            "Ray-march over the 240 m LOLA DEM with lunar curvature correction; "
            "no atmospheric refraction."
        ),
    }
