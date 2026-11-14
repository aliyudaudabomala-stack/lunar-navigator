"""Multi-scenario comparison endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ...models.schemas import CompareRequest
from ...services.analysis_service import compare
from ...services.sites import get_site
from ..deps import priorities_from_model

router = APIRouter(tags=["comparison"])


@router.post("/compare", summary="Rank 2–6 landing scenarios with a transparent score")
def run_compare(request: CompareRequest) -> dict:
    scenarios = []
    for scenario in request.scenarios:
        if scenario.site_id:
            site = get_site(scenario.site_id)
            if site is None:
                raise HTTPException(status_code=404, detail=f"Unknown site id '{scenario.site_id}'")
            scenarios.append(
                {
                    "site_id": site.id,
                    "lat": site.lat,
                    "lon": site.lon,
                    "name": scenario.name or site.name,
                    "datetime": scenario.datetime,
                    "window_days": scenario.window_days,
                    "step_minutes": scenario.step_minutes,
                }
            )
        else:
            scenarios.append(
                {
                    "lat": scenario.lat,
                    "lon": scenario.lon,
                    "name": scenario.name or "Custom site",
                    "datetime": scenario.datetime,
                    "window_days": scenario.window_days,
                    "step_minutes": scenario.step_minutes,
                }
            )

    result = compare(
        scenarios,
        priorities=priorities_from_model(request.priorities),
        include_timelines=request.include_timelines,
    )
    result["scenario_count"] = len(scenarios)
    return result
