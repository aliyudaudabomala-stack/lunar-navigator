"""Optional JPL Horizons cross-check client.

All mission calculations use the internal analytical ephemerides, so the app
remains fully reproducible offline. This client exists to let a reviewer ask
JPL Horizons for an independent az/el check when the network is available.

Failure is a first-class outcome: the caller always receives a structured
``unavailable`` status and the UI shows the offline-model result instead.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from ..core.config import get_settings
from ..scientific.time import isoformat_z, julian_date_tt, parse_datetime_utc

HORIZONS_LIMITATIONS = (
    "Horizons is an independent cross-check, not the computation used for the "
    "mission analysis. It is queried only on demand, may be rate-limited or "
    "unreachable, and its apparent az/el includes light-time and aberration "
    "corrections that differ slightly from the geometric local-horizon model."
)


def _cache_path(key: str) -> Path:
    settings = get_settings()
    directory = settings.cache_dir / "horizons"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{key}.json"


def _cache_key(body: str, when: datetime, lat: float, lon: float, elevation_m: float) -> str:
    raw = json.dumps(
        {
            "body": body,
            "when": when.isoformat(),
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "elevation_m": round(elevation_m, 3),
        },
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _build_params(body: str, when: datetime, lat: float, lon: float, elevation_m: float) -> dict[str, str]:
    command = {"sun": "10", "earth": "399", "moon": "301"}[body]
    jd = julian_date_tt(when)
    return {
        "format": "text",
        "COMMAND": f"'{command}'",
        "OBJ_DATA": "'NO'",
        "MAKE_EPHEM": "'YES'",
        "EPHEM_TYPE": "'OBSERVER'",
        "CENTER": "'coord@301'",
        "COORD_TYPE": "'GEODETIC'",
        "SITE_COORD": f"'{lon:.6f},{lat:.6f},{elevation_m / 1000.0:.4f}'",
        "TLIST": f"'{jd:.8f}'",
        "QUANTITIES": "'4,20'",
        "CSV_FORMAT": "'YES'",
        "ANG_FORMAT": "'DEG'",
        "TIME_DIGITS": "'SECONDS'",
        "EXTRA_PREC": "'YES'",
    }


def _parse_csv(text: str, body: str) -> tuple[list[dict[str, Any]], str | None]:
    """Parse Horizons CSV output without relying on fixed column positions."""

    if "$$SOE" not in text or "$$EOE" not in text:
        return [], "Horizons response did not contain an ephemeris block"

    header = ""
    for line in text.splitlines():
        if line.startswith("Date__(UT)") or line.startswith("Date___(UT)"):
            header = line
            break
    if not header:
        return [], "Horizons response did not contain a CSV header row"

    names = [part.strip() for part in header.split(",")]
    az_index = next((i for i, n in enumerate(names) if n.startswith("Azi")), None)
    el_index = next((i for i, n in enumerate(names) if n.startswith("Elev")), None)
    dist_index = next((i for i, n in enumerate(names) if n.startswith("delta")), None)
    if az_index is None or el_index is None:
        return [], "Horizons response did not expose azimuth/elevation columns"

    block = text.split("$$SOE", 1)[1].split("$$EOE", 1)[0]
    records: list[dict[str, Any]] = []
    for line in block.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) <= max(az_index, el_index):
            continue
        try:
            records.append(
                {
                    "body": body,
                    "time_utc": parts[0],
                    "azimuth_deg": round(float(parts[az_index]), 4),
                    "elevation_deg": round(float(parts[el_index]), 4),
                    "distance_km": (
                        round(float(parts[dist_index]), 3)
                        if dist_index is not None and len(parts) > dist_index
                        else None
                    ),
                }
            )
        except ValueError:
            continue
    if not records:
        return [], "Horizons returned no parsable ephemeris rows"
    return records, None


async def check_horizons(
    *,
    lat: float,
    lon: float,
    when: datetime,
    elevation_m: float = 0.0,
    ttl_seconds: int | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    when = parse_datetime_utc(when)
    retrieved_at: str | None = None
    started = time.perf_counter()
    records: list[dict[str, Any]] = []
    errors: list[str] = []

    if not settings.horizons_enabled:
        return {
            "status": "disabled",
            "requested_at_utc": isoformat_z(when),
            "retrieved_at": None,
            "source_url": settings.horizons_url,
            "records": [],
            "message": "Live Horizons cross-checks are disabled by configuration.",
            "limitations": HORIZONS_LIMITATIONS,
            "elapsed_ms": 0,
        }

    ttl = settings.horizons_cache_ttl_seconds if ttl_seconds is None else ttl_seconds
    cache_hits = 0

    async with httpx.AsyncClient(timeout=settings.horizons_timeout_seconds) as client:
        for body in ("sun", "earth"):
            key = _cache_key(body, when, lat, lon, elevation_m)
            path = _cache_path(key)
            if path.exists():
                try:
                    cached = json.loads(path.read_text(encoding="utf-8"))
                    age = time.time() - float(cached.get("_cached_at", 0))
                    if age <= ttl:
                        records.extend(cached["records"])
                        retrieved_at = cached.get("retrieved_at") or retrieved_at
                        cache_hits += 1
                        continue
                except (OSError, ValueError, KeyError):
                    pass

            params = _build_params(body, when, lat, lon, elevation_m)
            try:
                response = await client.get(settings.horizons_url, params=params)
                response.raise_for_status()
                parsed, parse_error = _parse_csv(response.text, body)
                if parse_error:
                    errors.append(f"{body}: {parse_error}")
                    continue
                now = isoformat_z(datetime.now(tz=timezone.utc))
                path.write_text(
                    json.dumps(
                        {"_cached_at": time.time(), "retrieved_at": now, "records": parsed},
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                records.extend(parsed)
                retrieved_at = retrieved_at or now
            except (httpx.HTTPError, OSError, ValueError) as exc:
                errors.append(f"{body}: {type(exc).__name__}: {exc}")

    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    if records and cache_hits == 2:
        status = "cached"
        message = "Both bodies came from the local Horizons cache within the configured TTL."
    elif records:
        status = "live" if cache_hits < 2 else "cached"
        message = (
            "JPL Horizons responded. Compare these values with the analytical model; "
            "small differences are expected."
        )
        if errors:
            message += " Partial failure: " + "; ".join(errors)
    else:
        status = "unavailable"
        message = (
            "JPL Horizons could not be reached from this deployment. The analytical "
            "ephemeris remains fully valid; no live cross-check is available."
        )
        if errors:
            message += " " + "; ".join(errors)

    return {
        "status": status,
        "requested_at_utc": isoformat_z(when),
        "retrieved_at": retrieved_at,
        "source_url": settings.horizons_url,
        "records": records,
        "message": message,
        "limitations": HORIZONS_LIMITATIONS,
        "elapsed_ms": elapsed_ms,
    }
