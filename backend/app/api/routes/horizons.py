"""Optional live JPL Horizons cross-check endpoint."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query

from ...services.horizons import check_horizons
from ...services.terrain_service import terrain_snapshot
from ..deps import resolve_site, resolve_when

router = APIRouter(prefix="/horizons", tags=["cross-check"])


@router.get("/check", summary="Ask JPL Horizons for an independent Sun/Earth az/el")
async def horizons_check(
    site_id: str | None = Query(None),
    lat: float | None = Query(None, ge=-90, le=90),
    lon: float | None = Query(None, ge=-360, le=360),
    datetime_: datetime | None = Query(None, alias="datetime"),
    elevation_m: float | None = Query(None, ge=-15000, le=20000),
) -> dict:
    _, lat0, lon0, _ = resolve_site(site_id=site_id, lat=lat, lon=lon)
    when = resolve_when(datetime_)
    if elevation_m is None:
        elevation_m = terrain_snapshot(lat0, lon0)["elevation_m"] or 0.0
    result = await check_horizons(
        lat=lat0, lon=lon0, when=when, elevation_m=float(elevation_m)
    )
    result["site"] = {"lat": lat0, "lon": lon0, "elevation_m": elevation_m}
    return result
