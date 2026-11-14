"""Candidate site catalogue endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ...services.sites import CANDIDATE_SITES, get_site

router = APIRouter(prefix="/sites", tags=["sites"])


@router.get("", summary="List candidate landing regions")
def list_candidates() -> dict:
    return {
        "count": len(CANDIDATE_SITES),
        "sites": [site.to_dict() for site in CANDIDATE_SITES],
        "disclaimer": (
            "Candidate regions for exploration and comparison. They are approximate "
            "centroids, not certified landing ellipses, and carry no safety certification."
        ),
    }


@router.get("/{site_id}", summary="Get one candidate landing region")
def get_candidate(site_id: str) -> dict:
    site = get_site(site_id)
    if site is None:
        raise HTTPException(status_code=404, detail=f"Unknown site id '{site_id}'")
    return site.to_dict()
