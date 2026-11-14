"""Terrain service: one shared DEM, cached horizon profiles and basemap rasters."""

from __future__ import annotations

from functools import lru_cache
import json
import math
from pathlib import Path
from threading import Lock

from ..core.config import get_settings
from ..scientific.terrain import (
    DEM_MAX_LAT,
    DEM_MIN_LAT,
    IllustrativeTerrain,
    LunarDem,
    load_terrain,
    sky_view_factor,
)

_terrain_lock = Lock()
_terrain = None
_horizon_cache: dict[tuple, dict] = {}


def get_terrain() -> LunarDem | IllustrativeTerrain:
    global _terrain
    if _terrain is None:
        with _terrain_lock:
            if _terrain is None:
                settings = get_settings()
                _terrain = load_terrain(settings.data_dir)
    return _terrain


def terrain_available() -> bool:
    return isinstance(get_terrain(), LunarDem)


def coverage_note(lat_deg: float, lon_deg: float) -> str:
    terrain = get_terrain()
    if isinstance(terrain, LunarDem):
        if terrain.contains(lat_deg, lon_deg):
            return "Covered by LOLA LDEM_75S_240M (75S to 90S)."
        return (
            "Outside the cached LOLA south-polar DEM (75S to 90S). The horizon is "
            "treated as a smooth spherical limb; no terrain obstruction is modelled."
        )
    return (
        "LOLA DEM not installed on this deployment. Terrain shown is illustrative "
        "synthetic data and must not be used for engineering decisions."
    )


def horizon_profile_for(lat_deg: float, lon_deg: float, *, az_step: float = 2.0, max_range_km: float = 30.0) -> dict:
    """Cached terrain horizon profile.

    Profiles are cached at 0.01 deg resolution (~300 m) so repeated dashboard
    and comparison requests are fast.
    """

    key = (round(lat_deg, 2), round(lon_deg, 2), float(az_step), float(max_range_km))
    if key in _horizon_cache:
        return _horizon_cache[key]

    terrain = get_terrain()
    if isinstance(terrain, LunarDem) and terrain.contains(lat_deg, lon_deg):
        profile = terrain.horizon_profile(
            lat_deg, lon_deg, azimuth_step_deg=az_step, max_range_km=max_range_km
        )
        profile["source_type"] = "lola-gdr"
    else:
        # Smooth spherical horizon: the Moon is treated as a perfect sphere.
        n = int(round(360.0 / az_step))
        profile = {
            "azimuths_deg": [i * az_step for i in range(n)],
            "elevations_deg": [0.0] * n,
            "distances_km": [None] * n,
            "site_elevation_m": None,
            "max_elevation_deg": 0.0,
            "mean_elevation_deg": 0.0,
            "min_elevation_deg": 0.0,
            "azimuth_step_deg": az_step,
            "max_range_km": max_range_km,
            "curvature_correction": False,
            "refraction": False,
            "source": "spherical-fallback",
            "method": "smooth spherical limb (no terrain data)",
        }
        if isinstance(terrain, IllustrativeTerrain) and terrain.contains(lat_deg, lon_deg):
            profile = terrain.horizon_profile(
                lat_deg, lon_deg, azimuth_step_deg=az_step, max_range_km=max_range_km
            )
            profile["source_type"] = "illustrative-fallback"

    profile["sky_view_factor"] = round(sky_view_factor(profile), 4)
    _horizon_cache[key] = profile
    return profile


def horizon_interpolator(profile: dict):
    elevations = profile["elevations_deg"]
    n = len(elevations)
    step = 360.0 / n

    def at(azimuth_deg: float) -> float:
        x = (azimuth_deg % 360.0) / step
        i0 = int(math.floor(x)) % n
        i1 = (i0 + 1) % n
        f = x - math.floor(x)
        return float(elevations[i0] + (elevations[i1] - elevations[i0]) * f)

    return at


def terrain_snapshot(lat_deg: float, lon_deg: float) -> dict:
    """Terrain descriptors used by dashboards, scoring and reports."""

    terrain = get_terrain()
    elevation = terrain.elevation_m(lat_deg, lon_deg)
    slope_and_aspect = terrain.slope_and_aspect(lat_deg, lon_deg)
    roughness = terrain.terrain_roughness(lat_deg, lon_deg)
    profile = horizon_profile_for(lat_deg, lon_deg)

    meta = terrain.metadata
    return {
        "source_type": profile.get("source_type", "spherical-fallback"),
        "product_id": meta.product_id,
        "dataset_id": meta.dataset_id,
        "source_url": meta.source_url,
        "retrieved_at": meta.retrieved_at,
        "resolution_m": meta.resolution_m,
        "projection": meta.projection,
        "coverage": meta.coverage,
        "vertical_datum": meta.vertical_datum,
        "available": meta.available,
        "elevation_m": None if elevation is None else round(elevation, 1),
        "slope_deg": None if slope_and_aspect is None else round(slope_and_aspect[0], 2),
        "aspect_deg": None if slope_and_aspect is None else round(slope_and_aspect[1], 1),
        "roughness_m": None if roughness is None else round(roughness, 1),
        "horizon": profile,
        "sky_view_factor": profile.get("sky_view_factor"),
        "coverage_note": coverage_note(lat_deg, lon_deg),
        "is_illustrative": not meta.available,
        "data_quality": (
            "measured (NASA LOLA GDR)"
            if meta.available and profile.get("source_type") == "lola-gdr"
            else "illustrative (synthetic)"
            if meta.available is False
            else "geometric (no terrain)"
        ),
    }


def dem_info() -> dict:
    settings = get_settings()
    terrain = get_terrain()
    meta = terrain.metadata
    label_path = settings.data_dir / "lola" / "ldem_75s_240m.lbl"
    try:
        label_present = label_path.exists()
    except OSError:
        label_present = False
    return {
        "product_id": meta.product_id,
        "dataset_id": meta.dataset_id,
        "source_url": meta.source_url,
        "retrieved_at": meta.retrieved_at,
        "resolution_m": meta.resolution_m,
        "projection": meta.projection,
        "reference_radius_m": meta.reference_radius_m,
        "vertical_datum": meta.vertical_datum,
        "coverage": meta.coverage,
        "file_bytes": meta.file_bytes,
        "sha256_prefix": meta.sha256,
        "available": meta.available,
        "label_file_present": label_present,
        "coverage_lat_range": [DEM_MIN_LAT, DEM_MAX_LAT],
        "horizon_cache_entries": len(_horizon_cache),
        "notes": (
            "Shape map (radius) at 240 m/pixel, true at the pole in south polar "
            "stereographic projection. Downloaded once from NASA PDS; not a live feed."
            if meta.available
            else "LOLA product not installed — synthetic fallback active."
        ),
    }


def basemap_png(size: int = 1400) -> tuple[bytes, dict]:
    terrain = get_terrain()
    return terrain.hillshade_png(size=size)


def clear_caches() -> None:
    _horizon_cache.clear()
