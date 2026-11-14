"""Full site analysis endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ...models.schemas import AnalyzeRequest
from ...services.analysis_service import analyze
from ..deps import priorities_from_model, resolve_site, resolve_when

router = APIRouter(tags=["analysis"])


@router.post("/analysis", summary="Full landing-site assessment")
def run_analysis(request: AnalyzeRequest) -> dict:
    site, lat, lon, name = resolve_site(
        site_id=request.site_id, lat=request.lat, lon=request.lon, name=request.name
    )
    when = resolve_when(request.datetime)
    try:
        return analyze(
            lat=lat,
            lon=lon,
            when=when,
            window_days=request.window_days,
            step_minutes=request.step_minutes,
            priorities=priorities_from_model(request.priorities),
            site_id=site.id if site else None,
            name=name,
            include_timeline=request.include_timeline,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
