"""Application-level analysis orchestration.

The service layer composes the scientific modules into payloads used by the API,
the comparison engine and the PDF report generator. Keeping this logic out of
the route handlers makes it unit-testable and reusable.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
from typing import Any

from ..scientific.constants import MOON_RADIUS_KM, SYNODIC_MONTH_DAYS
from ..scientific.frames import horizontal_to_body_vector, site_body_vector_km
from ..scientific.moon import lunar_ephemeris
from ..scientific.scoring import Priorities, build_assessment
from ..models.schemas import DEFAULT_MISSION_TIME
from ..scientific.time import (
    format_utc,
    isoformat_z,
    julian_date_tt,
    parse_datetime_utc,
)
from ..scientific.visibility import (
    analyze_site_visibility,
    build_timeline,
    sky_state,
    summarize_timeline,
)
from .sites import CandidateSite, get_site
from .terrain_service import (
    coverage_note,
    dem_info,
    get_terrain,
    horizon_interpolator,
    horizon_profile_for,
    terrain_snapshot,
)


def normalize_longitude(lon: float) -> float:
    """Normalise any longitude to [0, 360)."""

    return lon % 360.0


def make_time_limits(dt: datetime) -> list[float]:
    """Return the mission-time window boundaries in Julian dates."""

    jd = julian_date_tt(dt)
    return [jd - 1.0, jd + 1.0]


def provenance_records(*, horizons: dict | None = None) -> list[dict[str, Any]]:
    """Machine-readable provenance for every dataset/model used in a payload."""

    dem = dem_info()
    records: list[dict[str, Any]] = [
        {
            "name": "LRO Lunar Orbiter Laser Altimeter (LOLA) gridded topography",
            "product": dem["product_id"],
            "dataset_id": dem["dataset_id"],
            "url": dem["source_url"],
            "retrieved_at": dem["retrieved_at"],
            "units": "metres (radius relative to 1737.4 km sphere)",
            "frame": "mean Earth/polar axis, planetocentric latitude, east longitude",
            "status": "cached" if dem["available"] else "simulated",
            "limitations": (
                f"{dem['resolution_m']:.0f} m/pixel; south polar coverage only (75S–90S); "
                "no sub-pixel roughness or overhangs; horizon ray-march capped at 30 km."
                if dem["available"]
                else "LOLA product not installed; terrain is illustrative synthetic data."
            ),
        },
        {
            "name": "IAU WGCCRE lunar orientation (pck00010 rotational elements)",
            "product": "IAU 2015 Moon rotation model",
            "dataset_id": "IAU WGCCRE 2015",
            "url": "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/pck00010.tpc",
            "retrieved_at": None,
            "units": "degrees",
            "frame": "ICRF/J2000 to lunar body-fixed (mean Earth/polar axis)",
            "status": "modelled",
            "limitations": (
                "Analytical IAU model with periodic Cassini-state terms implemented in code; "
                "small physical-libration residuals (<0.01 deg) are below terrain resolution."
            ),
        },
        {
            "name": "Geocentric Sun/Moon ephemeris (Meeus, Astronomical Algorithms)",
            "product": "Analytical ELP-2000/82 truncation + VSOP87 solar series",
            "dataset_id": "Meeus 2nd edition, ch. 25 & 47",
            "url": "https://www.willbell.com/math/mc1.htm",
            "retrieved_at": None,
            "units": "degrees, km, AU",
            "frame": "geocentric ecliptic/equatorial of date, precessed to J2000",
            "status": "modelled",
            "limitations": (
                "Validated against Meeus Example 47.a: longitude within 0.0007 deg, "
                "latitude within 0.008 deg, distance within 25 km. No atmospheric refraction "
                "(the Moon has no atmosphere)."
            ),
        },
        {
            "name": "NASA/JPL Horizons system",
            "product": "Apparent az/el cross-check for Sun and Earth from a lunar site",
            "dataset_id": "JPL Horizons API",
            "url": "https://ssd.jpl.nasa.gov/horizons/",
            "retrieved_at": (horizons or {}).get("retrieved_at"),
            "units": "degrees",
            "frame": "observer topocentric, IAU_MOON body-fixed",
            "status": (horizons or {}).get("status", "not_requested"),
            "limitations": (
                "Optional live cross-check. The internal analytical model is used for all "
                "calculations so results remain reproducible without network access. "
                "Horizons availability is not guaranteed."
            ),
        },
        {
            "name": "USGS Gazetteer of Planetary Nomenclature",
            "product": "Named lunar feature coordinates",
            "dataset_id": "IAU WGCCRE gazetteer",
            "url": "https://planetarynames.wr.usgs.gov/",
            "retrieved_at": None,
            "units": "degrees",
            "frame": "planetocentric, east longitude",
            "status": "historical",
            "limitations": "Feature centres are reference points, not landing ellipses.",
        },
        {
            "name": "NASA Moon Trek",
            "product": "Lunar terrain exploration reference",
            "dataset_id": "Moon Trek",
            "url": "https://trek.nasa.gov/moon/",
            "retrieved_at": None,
            "units": "n/a",
            "frame": "n/a",
            "status": "reference",
            "limitations": (
                "Used as a visual/reference source; this deployment does not stream Moon Trek "
                "tiles and never presents its own rasters as Moon Trek data."
            ),
        },
    ]
    return records


def site_payload(site: CandidateSite | None, lat: float, lon: float, name: str | None = None) -> dict:
    if site is not None:
        payload = site.to_dict()
        payload["lat"] = site.lat
        payload["lon"] = site.lon
        payload["is_candidate_region"] = True
        return payload
    return {
        "id": "custom",
        "name": name or "Custom site",
        "short_name": name or "Custom site",
        "lat": lat,
        "lon": lon,
        "region": "Custom coordinates",
        "kind": "custom",
        "description": "User-defined selenographic coordinates.",
        "why_interesting": "",
        "coordinate_confidence": "user input",
        "source_note": "Entered by the user. Not validated against a landing-ellipse catalogue.",
        "color": "#4cc9f0",
        "is_candidate_region": True,
    }


def light_description(sun_el: float, horizon: float, visible: bool) -> str:
    if not visible:
        return "Shadowed (Sun below local terrain horizon)"
    if sun_el - horizon > 10:
        return "Full sunlight, high elevation"
    if sun_el - horizon > 3:
        return "Sunlit, moderate elevation"
    if sun_el - horizon > 0:
        return "Low grazing sunlight"
    return "Partial limb light"


def orientation_payload(jd_tt: float) -> dict:
    """Sub-solar/sub-Earth points and Moon phase for the 3D explorer."""

    eph = lunar_ephemeris(jd_tt)
    return {
        "subsolar_longitude_deg": round(eph.sub_solar_longitude_deg, 3),
        "subsolar_latitude_deg": round(eph.sub_solar_latitude_deg, 3),
        "subearth_longitude_deg": round(eph.sub_earth_longitude_deg, 3),
        "subearth_latitude_deg": round(eph.sub_earth_latitude_deg, 3),
        "phase_angle_deg": round(eph.phase_angle_deg, 3),
        "illuminated_fraction": round(eph.illuminated_fraction, 4),
        "sun_angular_radius_deg": round(eph.sun_angular_radius_deg, 4),
        "earth_angular_radius_deg": round(eph.earth_angular_radius_deg, 4),
        "moon_distance_km": round(eph.moon_distance_km, 1),
        "sun_distance_km": round(eph.sun_distance_from_moon_km, 1),
        "synodic_month_days": SYNODIC_MONTH_DAYS,
        "libration_latitude_deg": round(-eph.sub_earth_latitude_deg, 3),
        "libration_longitude_deg": round(-((eph.sub_earth_longitude_deg + 180) % 360 - 180), 3),
    }


def sky_payload(state) -> dict:
    return {
        "time_utc": isoformat_z(state.time_utc),
        "sun": {
            "azimuth_deg": round(state.sun_azimuth_deg, 3),
            "elevation_deg": round(state.sun_elevation_deg, 4),
            "angular_radius_deg": round(state.sun_angular_radius_deg, 4),
            "horizon_deg": round(state.horizon_sun_deg, 3),
            "margin_deg": round(state.sun_elevation_deg - state.horizon_sun_deg, 3),
            "above_horizon": state.sun_visible_center,
            "full_disk_above_horizon": state.sun_visible_disk,
            "description": light_description(
                state.sun_elevation_deg, state.horizon_sun_deg, state.sun_visible_center
            ),
        },
        "earth": {
            "azimuth_deg": round(state.earth_azimuth_deg, 3),
            "elevation_deg": round(state.earth_elevation_deg, 4),
            "angular_radius_deg": round(state.earth_angular_radius_deg, 4),
            "distance_km": round(state.earth_distance_km, 1),
            "horizon_deg": round(state.horizon_earth_deg, 3),
            "margin_deg": round(state.earth_elevation_deg - state.horizon_earth_deg, 3),
            "above_horizon": state.earth_visible_center,
            "full_disk_above_horizon": state.earth_visible_disk,
        },
        "subsolar_point": {
            "longitude_deg": round(state.subsolar_longitude_deg, 3),
            "latitude_deg": round(state.subsolar_latitude_deg, 3),
        },
        "sub_earth_point": {
            "longitude_deg": round(state.subearth_longitude_deg, 3),
            "latitude_deg": round(state.subearth_latitude_deg, 3),
        },
        "phase_angle_deg": round(state.phase_angle_deg, 3),
        "illuminated_fraction": round(state.illuminated_fraction, 4),
    }


def analyze(
    *,
    lat: float,
    lon: float,
    when: datetime,
    window_days: float = 7.0,
    step_minutes: int = 10,
    priorities: Priorities | None = None,
    site_id: str | None = None,
    name: str | None = None,
    horizons: dict | None = None,
    include_timeline: bool = True,
) -> dict:
    """Full site assessment used by the dashboard, comparison and reports."""

    lon = normalize_longitude(lon)
    when = parse_datetime_utc(when)
    priorities = priorities or Priorities()
    site = get_site(site_id) if site_id else None
    if site is not None:
        lat, lon = site.lat, site.lon

    terrain = terrain_snapshot(lat, lon)
    profile = terrain["horizon"]
    horizon_at = horizon_interpolator(profile)
    elevation_m = terrain["elevation_m"]

    state = sky_state(
        when,
        lat,
        lon,
        horizon_profile=profile,
        horizon_at=horizon_at,
        elevation_m=elevation_m,
    )

    window_end = when + timedelta(days=window_days)
    visibility = analyze_site_visibility(
        when,
        window_end,
        lat,
        lon,
        horizon_profile=profile,
        horizon_at=horizon_at,
        elevation_m=elevation_m,
        step_minutes=step_minutes,
    )
    summary = visibility["summary"]

    assessment = build_assessment(
        illumination=summary,
        comms=summary,
        terrain=terrain,
        landing_sun_margin_deg=state.sun_elevation_deg - state.horizon_sun_deg,
        landing_earth_margin_deg=state.earth_elevation_deg - state.horizon_earth_deg,
        priorities=priorities,
        site_name=site.name if site else (name or "Custom site"),
        window_days=window_days,
        window_start=format_utc(when),
        sun_visible_at_landing=state.sun_visible_center,
        earth_visible_at_landing=state.earth_visible_center,
        next_sunset_utc=summary.get("next_sunset_utc"),
    )

    jd_tt = julian_date_tt(when)
    orientation = orientation_payload(jd_tt)

    # Local horizon ring for the 3D scene (body-fixed unit vectors).
    horizon_ring = [
        {
            "azimuth_deg": az,
            "elevation_deg": el,
            "vector": horizontal_to_body_vector(az, el, lat, lon),
        }
        for az, el in zip(profile["azimuths_deg"], profile["elevations_deg"])
    ]

    site_vec = site_body_vector_km(lat, lon, elevation_m or 0.0)
    eph = lunar_ephemeris(jd_tt)

    payload = {
        "generated_at_utc": isoformat_z(datetime.now(tz=when.tzinfo)),
        "mode": "live-model" if terrain["source_type"] == "lola-gdr" else "demo-fallback",
        "site": site_payload(site, lat, lon, name),
        "time": {
            "utc": isoformat_z(when),
            "display_utc": format_utc(when),
            "julian_date_tt": round(jd_tt, 6),
            "window_start_utc": isoformat_z(when),
            "window_end_utc": isoformat_z(window_end),
            "window_days": window_days,
            "step_minutes": summary["step_minutes"],
        },
        "sky": sky_payload(state),
        "terrain": {k: v for k, v in terrain.items() if k != "horizon"},
        "horizon": {
            "profile": {
                "azimuths_deg": profile["azimuths_deg"],
                "elevations_deg": profile["elevations_deg"],
                "distances_km": profile["distances_km"],
                "azimuth_step_deg": profile["azimuth_step_deg"],
                "max_range_km": profile["max_range_km"],
                "source": profile["source"],
                "method": profile["method"],
                "curvature_correction": profile["curvature_correction"],
                "refraction": profile["refraction"],
                "max_elevation_deg": profile["max_elevation_deg"],
                "mean_elevation_deg": profile["mean_elevation_deg"],
            },
            "ring": horizon_ring,
        },
        "illumination": {
            "sun_visible_fraction": summary["sun_visible_fraction"],
            "sun_full_disk_fraction": summary["sun_full_disk_fraction"],
            "sunlight_hours": summary["sunlight_hours"],
            "windows": summary["sun_windows"],
            "window_count": summary["sun_window_count"],
            "longest_window_hours": summary["longest_sun_window_hours"],
            "mean_sun_elevation_deg": summary["mean_sun_elevation_deg"],
            "max_sun_elevation_deg": summary["max_sun_elevation_deg"],
            "min_sun_elevation_deg": summary["min_sun_elevation_deg"],
            "mean_horizon_deg": summary["mean_sun_horizon_deg"],
            "next_sunset_utc": summary["next_sunset_utc"],
            "next_sunrise_utc": summary["next_sunrise_utc"],
            "sample_count": summary["sample_count"],
            "step_minutes": summary["step_minutes"],
            "span_hours": summary["span_hours"],
        },
        "comms": {
            "earth_visible_fraction": summary["earth_visible_fraction"],
            "earth_visible_hours": summary["earth_visible_hours"],
            "windows": summary["earth_windows"],
            "window_count": summary["earth_window_count"],
            "longest_window_hours": summary["longest_earth_window_hours"],
            "mean_earth_elevation_deg": summary["mean_earth_elevation_deg"],
            "max_earth_elevation_deg": summary["max_earth_elevation_deg"],
            "min_earth_elevation_deg": summary["min_earth_elevation_deg"],
            "next_earthset_utc": summary["next_earthset_utc"],
            "next_earthrise_utc": summary["next_earthrise_utc"],
            "link_note": (
                "Geometric line-of-sight only. A real DTE link also depends on antenna "
                "pointing, blockage, transmit power, data rate and link budget."
            ),
        },
        "orientation": orientation,
        "assessment": assessment,
        "timeline": visibility["timeline"] if include_timeline else [],
        "provenance": provenance_records(horizons=horizons),
        "assumptions": [
            "All times are UTC; TT-UTC = 69.184 s.",
            "Site coordinates are planetocentric selenographic latitude/longitude (east positive).",
            "The Moon is treated as a sphere of radius 1737.4 km for site geometry.",
            "No atmospheric refraction (the Moon has no atmosphere).",
            "Horizon profiles use a 30 km ray-march over the 240 m LOLA DEM with curvature correction.",
            "Earth visibility is geometric; it is not a radio link-budget calculation.",
            "Solar power estimates ignore hardware efficiency, dust, incidence-angle losses and battery state.",
        ],
        "limitations": [
            "The 240 m/px DEM cannot resolve lander-scale hazards (rocks, small scarps, overhangs).",
            "Horizon rays stop at 30 km; distant massifs beyond that range are not included in every direction.",
            "Physical libration residuals and polar motion are below the terrain-model uncertainty.",
            "Scoring weights are user-selected heuristics, not NASA flight rules.",
            "Candidate-site coordinates are approximate region centroids, not certified landing ellipses.",
        ],
        "local_frame": {
            "site_vector_km": [round(v, 3) for v in site_vec],
            "moon_radius_km": MOON_RADIUS_KM,
            "note": "Vectors are in the lunar body-fixed frame for the 3D explorer.",
        },
        "visibility_summary": summary,
        "earth_direction_body": [round(v, 6) for v in eph.earth_direction_j2000],
    }

    # Compute the Earth/Sun body-fixed direction used by the 3D view (body
    # coordinates are already available through the horizon ring transform).
    return payload


def compare(
    scenarios: list[dict],
    *,
    priorities: Priorities | None = None,
    include_timelines: bool = False,
) -> dict:
    """Analyse 2-4 scenarios and rank them with a transparent score."""

    results = []
    for scenario in scenarios:
        result = analyze(
            lat=scenario["lat"],
            lon=scenario["lon"],
            when=scenario.get("datetime") or DEFAULT_MISSION_TIME,
            window_days=scenario.get("window_days", 7.0),
            step_minutes=scenario.get("step_minutes", 15),
            priorities=priorities,
            site_id=scenario.get("site_id"),
            name=scenario.get("name"),
            include_timeline=include_timelines,
        )
        results.append(result)

    ranked = sorted(results, key=lambda r: r["assessment"]["score"], reverse=True)
    best = ranked[0]
    ranking = []
    for index, result in enumerate(ranked, start=1):
        ranking.append(
            {
                "rank": index,
                "site": result["site"]["short_name"],
                "site_id": result["site"]["id"],
                "score": result["assessment"]["score"],
                "grade": result["assessment"]["grade"],
                "sun_visible_fraction": result["illumination"]["sun_visible_fraction"],
                "earth_visible_fraction": result["comms"]["earth_visible_fraction"],
                "slope_deg": result["terrain"]["slope_deg"],
                "elevation_m": result["terrain"]["elevation_m"],
                "time_utc": result["time"]["utc"],
            }
        )
    return {
        "generated_at_utc": isoformat_z(datetime.now(tz=timezone.utc)),
        "priorities": priorities.normalized() if priorities else Priorities().normalized(),
        "scenarios": results,
        "ranking": ranking,
        "recommendation": {
            "site": best["site"]["short_name"],
            "score": best["assessment"]["score"],
            "summary": (
                f"Under the selected priorities, {best['site']['short_name']} has the highest "
                f"planning score ({best['assessment']['score']:.1f}/100). "
                f"{best['assessment']['advantages'][0] if best['assessment']['advantages'] else ''} "
                "Treat this as a starting point for trade studies, not a flight decision."
            ),
        },
        "disclaimer": (
            "Ranking is relative to the scenarios entered, using user-selected weights. "
            "It does not establish landing safety or mission feasibility."
        ),
    }


def local_terrain_window(lat: float, lon: float, span_km: float = 40.0, size: int = 120) -> dict:
    """Small elevation raster for local terrain visualisation."""

    terrain = get_terrain()
    if getattr(terrain, "metadata").available and not terrain.contains(lat, lon):
        return {"available": False, "reason": "outside LOLA polar coverage", "grid": None}

    half = span_km / 2.0
    xs = [(-half + span_km * i / (size - 1)) for i in range(size)]
    ys = [(-half + span_km * j / (size - 1)) for j in range(size)]
    grid = []
    for y in ys:
        row = []
        for x in xs:
            dlat = math.degrees(y / MOON_RADIUS_KM)
            dlon = math.degrees(x / (MOON_RADIUS_KM * math.cos(math.radians(lat))))
            row.append(terrain.elevation_m(lat + dlat, lon + dlon))
        grid.append(row)
    values = [v for row in grid for v in row if v is not None]
    return {
        "available": bool(values),
        "span_km": span_km,
        "size": size,
        "min_m": min(values) if values else None,
        "max_m": max(values) if values else None,
        "grid": grid,
        "source_type": "lola-gdr" if getattr(terrain, "metadata").available else "illustrative-fallback",
    }


def sample_series(
    *,
    lat: float,
    lon: float,
    start: datetime,
    end: datetime,
    step_minutes: int = 10,
    site_id: str | None = None,
) -> dict:
    """Sky timeline for the analyzer pages (no full assessment)."""

    site = get_site(site_id) if site_id else None
    if site is not None:
        lat, lon = site.lat, site.lon
    lon = normalize_longitude(lon)
    terrain = terrain_snapshot(lat, lon)
    profile = terrain["horizon"]
    horizon_at = horizon_interpolator(profile)
    rows = build_timeline(
        start,
        end,
        lat,
        lon,
        horizon_profile=profile,
        horizon_at=horizon_at,
        elevation_m=terrain["elevation_m"],
        step_minutes=step_minutes,
    )
    return {
        "site": site_payload(site, lat, lon),
        "terrain": {k: v for k, v in terrain.items() if k != "horizon"},
        "horizon": {
            "azimuths_deg": profile["azimuths_deg"],
            "elevations_deg": profile["elevations_deg"],
            "max_elevation_deg": profile["max_elevation_deg"],
            "source": profile["source"],
        },
        "timeline": rows,
        "summary": summarize_timeline(rows),
        "provenance": provenance_records(),
        "assumptions": [
            "No atmospheric refraction is applied.",
            "Visibility is geometric relative to the terrain horizon.",
            "Solar and Earth positions are analytical ephemerides, not live Horizons data.",
        ],
    }
