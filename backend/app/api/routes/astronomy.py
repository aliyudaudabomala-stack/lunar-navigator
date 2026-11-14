"""Sky geometry, timelines and Moon orientation endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Query

from ...api.deps import resolve_site, resolve_when
from ...core.config import get_settings
from ...scientific.time import isoformat_z, julian_date_tt, parse_datetime_utc
from ...scientific.visibility import build_timeline, sky_state, summarize_timeline
from ...services.analysis_service import orientation_payload, sky_payload, site_payload
from ...services.terrain_service import (
    horizon_interpolator,
    horizon_profile_for,
    terrain_snapshot,
)

router = APIRouter(prefix="/astronomy", tags=["astronomy"])


def _site_geometry(site_id: str | None, lat: float | None, lon: float | None) -> tuple[Any, float, float, dict]:
    site, lat0, lon0, _ = resolve_site(site_id=site_id, lat=lat, lon=lon)
    terrain = terrain_snapshot(lat0, lon0)
    return site, lat0, lon0, terrain


@router.get("/sky", summary="Sun and Earth az/el at one instant")
def sky(
    site_id: str | None = Query(None),
    lat: float | None = Query(None, ge=-90, le=90),
    lon: float | None = Query(None, ge=-360, le=360),
    datetime_: datetime | None = Query(None, alias="datetime"),
) -> dict:
    site, lat0, lon0, terrain = _site_geometry(site_id, lat, lon)
    when = parse_datetime_utc(resolve_when(datetime_))
    profile = terrain["horizon"]
    state = sky_state(
        when,
        lat0,
        lon0,
        horizon_profile=profile,
        horizon_at=horizon_interpolator(profile),
        elevation_m=terrain["elevation_m"],
    )
    return {
        "site": site_payload(site, lat0, lon0),
        "time_utc": isoformat_z(when),
        "sky": sky_payload(state),
        "terrain": {k: v for k, v in terrain.items() if k != "horizon"},
        "provenance": {
            "ephemeris": "Analytical Meeus/IAU model (not live Horizons)",
            "terrain": terrain["data_quality"],
            "product_id": terrain["product_id"],
        },
    }


@router.get("/series", summary="Sun/Earth elevation timeline")
def series(
    site_id: str | None = Query(None),
    lat: float | None = Query(None, ge=-90, le=90),
    lon: float | None = Query(None, ge=-360, le=360),
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    step_minutes: int = Query(30, ge=1, le=120),
) -> dict:
    settings = get_settings()
    site, lat0, lon0, terrain = _site_geometry(site_id, lat, lon)
    start_dt = parse_datetime_utc(resolve_when(start))
    end_dt = parse_datetime_utc(end) if end else start_dt + timedelta(days=settings.default_window_days)
    if end_dt <= start_dt:
        end_dt = start_dt + timedelta(days=1)
    profile = terrain["horizon"]
    rows = build_timeline(
        start_dt,
        end_dt,
        lat0,
        lon0,
        horizon_profile=profile,
        horizon_at=horizon_interpolator(profile),
        elevation_m=terrain["elevation_m"],
        step_minutes=step_minutes,
        max_samples=settings.max_timeline_samples,
    )
    return {
        "site": site_payload(site, lat0, lon0),
        "start_utc": isoformat_z(start_dt),
        "end_utc": isoformat_z(end_dt),
        "requested_step_minutes": step_minutes,
        "effective_step_minutes": summarize_timeline(rows)["step_minutes"],
        "sample_count": len(rows),
        "terrain": {k: v for k, v in terrain.items() if k != "horizon"},
        "summary": summarize_timeline(rows),
        "timeline": rows,
        "limitations": [
            "Geometric visibility only; no atmospheric refraction.",
            "Direct-to-Earth visibility is not a radio link-budget calculation.",
            "Timeline edges are limited by the sampling step.",
        ],
    }


@router.get("/orientation", summary="Sub-Earth/sub-solar points and Moon phase")
def orientation(datetime_: datetime | None = Query(None, alias="datetime")) -> dict:
    when = parse_datetime_utc(resolve_when(datetime_))
    payload = orientation_payload(julian_date_tt(when))
    payload["time_utc"] = isoformat_z(when)
    payload["reference_frame"] = "IAU Moon body-fixed (mean Earth/polar axis), east longitude"
    return payload
