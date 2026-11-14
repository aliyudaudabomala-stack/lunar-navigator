"""PDF report download endpoint."""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Response

from ...models.schemas import ReportRequest
from ...services.analysis_service import analyze
from ...services.reports import build_report
from ..deps import priorities_from_model, resolve_site, resolve_when

router = APIRouter(prefix="/reports", tags=["reports"])


def _safe_filename(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-")
    return (slug or "site")[:60]


@router.post(
    "/pdf",
    summary="Generate a PDF mission report",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
def pdf_report(request: ReportRequest) -> Response:
    site, lat, lon, name = resolve_site(
        site_id=request.site_id, lat=request.lat, lon=request.lon, name=request.name
    )
    when = resolve_when(request.datetime)
    try:
        payload = analyze(
            lat=lat,
            lon=lon,
            when=when,
            window_days=request.window_days,
            step_minutes=request.step_minutes,
            priorities=priorities_from_model(request.priorities),
            site_id=site.id if site else None,
            name=name,
            include_timeline=True,
        )
        pdf = build_report(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive, reportlab can fail on fonts
        raise HTTPException(status_code=500, detail=f"Report generation failed: {exc}") from exc

    filename = f"lunar-navigator-{_safe_filename(payload['site']['short_name'])}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Report-Site": payload["site"]["short_name"],
            "X-Report-Score": str(payload["assessment"]["score"]),
        },
    )
