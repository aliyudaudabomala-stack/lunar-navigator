"""Shared request helpers for API routes."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException

from ..models.schemas import DEFAULT_MISSION_TIME, PrioritiesModel
from ..scientific.scoring import Priorities
from ..services.sites import CandidateSite, get_site


def resolve_site(
    *,
    site_id: str | None,
    lat: float | None,
    lon: float | None,
    name: str | None = None,
) -> tuple[CandidateSite | None, float, float, str | None]:
    if site_id:
        site = get_site(site_id)
        if site is None:
            raise HTTPException(status_code=404, detail=f"Unknown site id '{site_id}'")
        return site, site.lat, site.lon, site.name
    if lat is None or lon is None:
        raise HTTPException(status_code=422, detail="Provide site_id or both lat and lon")
    if not -90.0 <= lat <= 90.0:
        raise HTTPException(status_code=422, detail="lat must be within [-90, 90]")
    return None, float(lat), float(lon) % 360.0, name


def resolve_when(value: datetime | None) -> datetime:
    return value or DEFAULT_MISSION_TIME


def priorities_from_model(model: PrioritiesModel) -> Priorities:
    return Priorities(
        power=model.power,
        comms=model.comms,
        terrain=model.terrain,
        timing=model.timing,
    )
