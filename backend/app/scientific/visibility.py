"""Sunlight and direct-to-Earth visibility analysis.

Distinctions that matter scientifically
---------------------------------------
* **Geometric visibility** means the centre of the Sun/Earth is above the local
  terrain horizon. It is *not* a power or link-budget prediction.
* **Limb-aware visibility** additionally requires the whole disk to clear the
  horizon (used for "full-disk" sunlight and a conservative comms geometry).
* Lunar sunrise/sunset are caused by terrain and the Moon's rotation; there is
  no atmosphere, so no refraction is applied anywhere.
* Direct-to-Earth (DTE) *geometry* is necessary but not sufficient for a radio
  link: antenna pointing, blockage, multipath, transmit power and the link
  budget must be analysed separately.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
from typing import Callable, Iterable

import numpy as np

from .constants import SUN_ANGULAR_RADIUS_DEG
from .frames import (
    local_sky_position,
    site_body_vector_km,
)
from .moon import LunarEphemeris, lunar_ephemeris, target_vectors_body
from .time import isoformat_z, julian_date_tt, parse_datetime_utc


@dataclass(frozen=True)
class SkyState:
    """Instantaneous geometry at a site."""

    time_utc: datetime
    sun_azimuth_deg: float
    sun_elevation_deg: float
    sun_angular_radius_deg: float
    earth_azimuth_deg: float
    earth_elevation_deg: float
    earth_angular_radius_deg: float
    earth_distance_km: float
    horizon_sun_deg: float
    horizon_earth_deg: float
    sun_visible_center: bool
    sun_visible_disk: bool
    earth_visible_center: bool
    earth_visible_disk: bool
    subsolar_longitude_deg: float
    subsolar_latitude_deg: float
    subearth_longitude_deg: float
    subearth_latitude_deg: float
    phase_angle_deg: float
    illuminated_fraction: float



def sky_state(
    when: datetime,
    lat_deg: float,
    lon_deg: float,
    *,
    horizon_profile: dict,
    horizon_at: Callable[[float], float],
    elevation_m: float | None = None,
) -> SkyState:
    """Compute Sun and Earth geometry for one instant and site."""

    dt = parse_datetime_utc(when)
    jd_tt = julian_date_tt(dt)
    eph = lunar_ephemeris(jd_tt)
    earth_vec, sun_vec = target_vectors_body(eph)

    site = site_body_vector_km(lat_deg, lon_deg, elevation_m or 0.0)
    sun = local_sky_position(sun_vec, site, target_radius_km=695_700.0)
    earth = local_sky_position(earth_vec, site, target_radius_km=6378.137)

    h_sun = horizon_at(sun.azimuth_deg)
    h_earth = horizon_at(earth.azimuth_deg)

    # Conservative: the entire solar disk must clear the terrain.
    sun_disk = sun.elevation_deg - sun.angular_radius_deg > h_sun
    earth_disk = earth.elevation_deg - earth.angular_radius_deg > h_earth

    return SkyState(
        time_utc=dt,
        sun_azimuth_deg=sun.azimuth_deg,
        sun_elevation_deg=sun.elevation_deg,
        sun_angular_radius_deg=sun.angular_radius_deg,
        earth_azimuth_deg=earth.azimuth_deg,
        earth_elevation_deg=earth.elevation_deg,
        earth_angular_radius_deg=earth.angular_radius_deg,
        earth_distance_km=earth.distance_km,
        horizon_sun_deg=h_sun,
        horizon_earth_deg=h_earth,
        sun_visible_center=sun.elevation_deg > h_sun,
        sun_visible_disk=sun_disk,
        earth_visible_center=earth.elevation_deg > h_earth,
        earth_visible_disk=earth_disk,
        subsolar_longitude_deg=eph.sub_solar_longitude_deg,
        subsolar_latitude_deg=eph.sub_solar_latitude_deg,
        subearth_longitude_deg=eph.sub_earth_longitude_deg,
        subearth_latitude_deg=eph.sub_earth_latitude_deg,
        phase_angle_deg=eph.phase_angle_deg,
        illuminated_fraction=eph.illuminated_fraction,
    )


def build_timeline(
    start: datetime,
    end: datetime,
    lat_deg: float,
    lon_deg: float,
    *,
    horizon_profile: dict,
    horizon_at: Callable[[float], float],
    elevation_m: float | None = None,
    step_minutes: int = 10,
    max_samples: int = 5000,
) -> list[dict]:
    """Sample sky-state over an interval.

    A maximum sample count is enforced so a careless request cannot exhaust the
    server; the effective step is increased and reported to the client.
    """

    start_utc = parse_datetime_utc(start)
    end_utc = parse_datetime_utc(end)
    if end_utc <= start_utc:
        raise ValueError("Timeline end must be after start")

    total_minutes = (end_utc - start_utc).total_seconds() / 60.0
    effective_step = max(float(step_minutes), total_minutes / max_samples)
    count = int(math.floor(total_minutes / effective_step)) + 1
    rows: list[dict] = []

    for i in range(count):
        when = start_utc + timedelta(minutes=i * effective_step)
        st = sky_state(
            when,
            lat_deg,
            lon_deg,
            horizon_profile=horizon_profile,
            horizon_at=horizon_at,
            elevation_m=elevation_m,
        )
        rows.append(
            {
                "time": isoformat_z(st.time_utc),
                "sun_azimuth_deg": round(st.sun_azimuth_deg, 3),
                "sun_elevation_deg": round(st.sun_elevation_deg, 4),
                "sun_horizon_deg": round(st.horizon_sun_deg, 3),
                "sun_visible": st.sun_visible_center,
                "sun_full_disk": st.sun_visible_disk,
                "earth_azimuth_deg": round(st.earth_azimuth_deg, 3),
                "earth_elevation_deg": round(st.earth_elevation_deg, 4),
                "earth_horizon_deg": round(st.horizon_earth_deg, 3),
                "earth_visible": st.earth_visible_center,
                "earth_full_disk": st.earth_visible_disk,
                "earth_distance_km": round(st.earth_distance_km, 1),
                "phase_angle_deg": round(st.phase_angle_deg, 2),
                "illuminated_fraction": round(st.illuminated_fraction, 4),
                "subsolar_latitude_deg": round(st.subsolar_latitude_deg, 3),
            }
        )

    return rows


@dataclass(frozen=True)
class Window:
    start: datetime
    end: datetime | None
    state_at_start: str
    state_at_end: str

    @property
    def duration_hours(self) -> float | None:
        if self.end is None:
            return None
        return (self.end - self.start).total_seconds() / 3600.0


def extract_windows(
    rows: list[dict],
    flag_key: str,
    *,
    start_padding: bool = True,
) -> list[dict]:
    """Convert a boolean timeline into visibility windows with interpolated edges."""

    windows: list[dict] = []
    if not rows:
        return windows

    times = [parse_datetime_utc(r["time"]) for r in rows]
    flags = [bool(r[flag_key]) for r in rows]

    def crossing_time(i0: int, i1: int) -> datetime:
        """Linear interpolation of the flag transition (timeline resolution)."""

        t0, t1 = times[i0], times[i1]
        return t0 + (t1 - t0) * 0.5

    i = 0
    n = len(flags)
    while i < n:
        if flags[i]:
            j = i
            while j + 1 < n and flags[j + 1]:
                j += 1
            begin = times[i] if i == 0 else crossing_time(i - 1, i)
            finish = times[j] if j == n - 1 else crossing_time(j, j + 1)
            duration = (finish - begin).total_seconds() / 3600.0
            windows.append(
                {
                    "start": isoformat_z(begin),
                    "end": isoformat_z(finish),
                    "duration_hours": round(duration, 3),
                    "clipped_start": i == 0,
                    "clipped_end": j == n - 1,
                }
            )
            i = j + 1
        else:
            i += 1

    return windows


def _duration_fraction(rows: list[dict], flag_key: str) -> float:
    if len(rows) < 2:
        return 0.0
    return sum(1 for r in rows if r[flag_key]) / len(rows)


def _longest_window(windows: Iterable[dict]) -> dict | None:
    best = None
    for w in windows:
        if best is None or w["duration_hours"] > best["duration_hours"]:
            best = w
    return best


def _next_transition(rows: list[dict], flag_key: str) -> dict | None:
    """Find the next change of a visibility flag inside the sampled window."""

    for i in range(1, len(rows)):
        if bool(rows[i][flag_key]) != bool(rows[i - 1][flag_key]):
            return {
                "time": rows[i]["time"],
                "from": bool(rows[i - 1][flag_key]),
                "to": bool(rows[i][flag_key]),
                "resolution_minutes": _row_spacing_minutes(rows),
            }
    return None


def _row_spacing_minutes(rows: list[dict]) -> float:
    if len(rows) < 2:
        return 0.0
    t0 = parse_datetime_utc(rows[0]["time"])
    t1 = parse_datetime_utc(rows[1]["time"])
    return round((t1 - t0).total_seconds() / 60.0, 3)


def summarize_timeline(rows: list[dict]) -> dict:
    """Derive illumination/comms statistics and windows from a timeline."""

    sun_windows = extract_windows(rows, "sun_visible")
    earth_windows = extract_windows(rows, "earth_visible")
    sun_fraction = _duration_fraction(rows, "sun_visible")
    earth_fraction = _duration_fraction(rows, "earth_visible")
    sun_full_fraction = _duration_fraction(rows, "sun_full_disk")

    sun_values = [r["sun_elevation_deg"] for r in rows]
    earth_values = [r["earth_elevation_deg"] for r in rows]
    sun_horizons = [r["sun_horizon_deg"] for r in rows]

    spacing = max(_row_spacing_minutes(rows), 1e-6)
    span_hours = (parse_datetime_utc(rows[-1]["time"]) - parse_datetime_utc(rows[0]["time"])).total_seconds() / 3600.0

    # Time remaining until the next sunset (sun goes from visible to hidden).
    next_sunset = None
    for i in range(1, len(rows)):
        if rows[i - 1]["sun_visible"] and not rows[i]["sun_visible"]:
            next_sunset = rows[i]["time"]
            break
    next_sunrise = None
    for i in range(1, len(rows)):
        if not rows[i - 1]["sun_visible"] and rows[i]["sun_visible"]:
            next_sunrise = rows[i]["time"]
            break

    return {
        "sample_count": len(rows),
        "step_minutes": spacing,
        "span_hours": round(span_hours, 2),
        "sun_visible_fraction": round(sun_fraction, 4),
        "sun_full_disk_fraction": round(sun_full_fraction, 4),
        "sunlight_hours": round(sun_fraction * span_hours, 2),
        "sun_windows": sun_windows,
        "sun_window_count": len(sun_windows),
        "longest_sun_window_hours": round(_longest_window(sun_windows)["duration_hours"], 2)
        if sun_windows
        else 0.0,
        "next_sunset_utc": next_sunset,
        "next_sunrise_utc": next_sunrise,
        "mean_sun_elevation_deg": round(float(np.mean(sun_values)), 3),
        "max_sun_elevation_deg": round(float(np.max(sun_values)), 3),
        "min_sun_elevation_deg": round(float(np.min(sun_values)), 3),
        "mean_sun_horizon_deg": round(float(np.mean(sun_horizons)), 3),
        "earth_visible_fraction": round(earth_fraction, 4),
        "earth_visible_hours": round(earth_fraction * span_hours, 2),
        "earth_windows": earth_windows,
        "earth_window_count": len(earth_windows),
        "longest_earth_window_hours": round(_longest_window(earth_windows)["duration_hours"], 2)
        if earth_windows
        else 0.0,
        "mean_earth_elevation_deg": round(float(np.mean(earth_values)), 3),
        "max_earth_elevation_deg": round(float(np.max(earth_values)), 3),
        "min_earth_elevation_deg": round(float(np.min(earth_values)), 3),
        "next_earthset_utc": next(
            (rows[i]["time"] for i in range(1, len(rows)) if rows[i - 1]["earth_visible"] and not rows[i]["earth_visible"]),
            None,
        ),
        "next_earthrise_utc": next(
            (rows[i]["time"] for i in range(1, len(rows)) if not rows[i - 1]["earth_visible"] and rows[i]["earth_visible"]),
            None,
        ),
        "next_transition": _next_transition(rows, "sun_visible"),
    }


def analyze_site_visibility(
    start: datetime,
    end: datetime,
    lat_deg: float,
    lon_deg: float,
    *,
    horizon_profile: dict,
    horizon_at: Callable[[float], float],
    elevation_m: float | None,
    step_minutes: int = 10,
) -> dict:
    rows = build_timeline(
        start,
        end,
        lat_deg,
        lon_deg,
        horizon_profile=horizon_profile,
        horizon_at=horizon_at,
        elevation_m=elevation_m,
        step_minutes=step_minutes,
    )
    return {"timeline": rows, "summary": summarize_timeline(rows)}
