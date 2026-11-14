"""Candidate landing regions.

IMPORTANT: these are *exploration candidates*, not certified or approved
landing sites. Coordinates are approximate centroids chosen for demonstration
and are flagged as such throughout the API and UI. Every value here is a
starting point that the user can edit.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class CandidateSite:
    id: str
    name: str
    short_name: str
    lat: float
    lon: float
    region: str
    kind: str
    description: str
    why_interesting: str
    coordinate_confidence: str
    source_note: str
    color: str

    def to_dict(self) -> dict:
        return asdict(self)


CANDIDATE_SITES: tuple[CandidateSite, ...] = (
    CandidateSite(
        id="shackleton-rim",
        name="Shackleton Rim — Candidate Region",
        short_name="Shackleton Rim",
        lat=-89.295,
        lon=129.6,
        region="Shackleton / South Pole",
        kind="candidate-region",
        description=(
            "High ground on the north-eastern rim of Shackleton crater, about 8 km "
            "from the lunar south pole. The crater floor is permanently shadowed while "
            "this rim remains sunlit through the polar day."
        ),
        why_interesting=(
            "Combines access to permanently shadowed terrain (volatiles) with "
            "near-continuous solar power on adjacent high ground."
        ),
        coordinate_confidence="approximate (region centroid, ±2 km)",
        source_note=(
            "Coordinates selected from the LOLA LDEM_75S_240M product around the published "
            "Shackleton centre (89.67S, 129.78E, IAU/USGS Gazetteer). Not a certified site."
        ),
        color="#4cc9f0",
    ),
    CandidateSite(
        id="connecting-ridge",
        name="Connecting Ridge — Candidate Region",
        short_name="Connecting Ridge",
        lat=-89.45,
        lon=222.7,
        region="Shackleton–de Gerlache ridge",
        kind="candidate-region",
        description=(
            "Broad ridge connecting the Shackleton and de Gerlache crater rims. The "
            "ridge offers long illumination windows and relatively gentle local slopes."
        ),
        why_interesting=(
            "Frequently cited in Artemis-era south-pole landing studies for its "
            "combination of illumination and proximity to shadowed regions."
        ),
        coordinate_confidence="approximate (region centroid, ±5 km)",
        source_note=(
            "Illustrative centroid of the connecting ridge used in NASA/CLPS south-pole "
            "studies; verify against the current project traverse analysis."
        ),
        color="#8b5cf6",
    ),
    CandidateSite(
        id="malapert-massif",
        name="Malapert Massif — Candidate Region",
        short_name="Malapert Massif",
        lat=-86.0,
        lon=2.9,
        region="Malapert Massif",
        kind="candidate-region",
        description=(
            "A high massif about 180 km from the south pole, rising roughly 5 km above "
            "the surrounding terrain. Its summit has a wide view of the sky and Earth."
        ),
        why_interesting=(
            "Potential for long direct-to-Earth visibility and elevated solar exposure, "
            "at the cost of distance from the pole's shadowed volatiles."
        ),
        coordinate_confidence="approximate (summit area, ±5 km)",
        source_note=(
            "Summit coordinates identified from LOLA topography near the Malapert Massif "
            "described in lunar south-pole literature. Not a certified site."
        ),
        color="#fbbf24",
    ),
    CandidateSite(
        id="de-gerlache-rim",
        name="de Gerlache Rim — Candidate Region",
        short_name="de Gerlache Rim",
        lat=-89.0,
        lon=263.8,
        region="de Gerlache / South Pole",
        kind="candidate-region",
        description=(
            "Rim terrain of de Gerlache crater, one of the permanently shadowed regions "
            "near the south pole. Local relief creates strongly asymmetric lighting."
        ),
        why_interesting=(
            "Science target adjacent to cold traps; illumination is highly sensitive to "
            "exact position on the rim."
        ),
        coordinate_confidence="approximate (rim region, ±5 km)",
        source_note=(
            "Rim point selected from LOLA topography near the IAU Gazetteer de Gerlache "
            "centre; local micro-site selection requires higher-resolution data."
        ),
        color="#34d399",
    ),
    CandidateSite(
        id="cabeus",
        name="Cabeus Floor — Candidate Region",
        short_name="Cabeus Floor",
        lat=-85.33,
        lon=317.87,
        region="Cabeus",
        kind="candidate-region",
        description=(
            "Large, deep crater near the south pole whose floor is permanently shadowed. "
            "LCROSS impacted inside Cabeus in 2009 and detected water-bearing material."
        ),
        why_interesting=(
            "High-value volatile science, but very poor solar power and challenging "
            "communications geometry from the floor."
        ),
        coordinate_confidence="approximate (crater centroid, ±10 km)",
        source_note=(
            "IAU Gazetteer coordinates; LCROSS target site. Illustration of a "
            "science-first, power-poor scenario."
        ),
        color="#f87171",
    ),
    CandidateSite(
        id="nobile-rim",
        name="Nobile Rim — Candidate Region",
        short_name="Nobile Rim",
        lat=-87.2,
        lon=50.0,
        region="Nobile / South Pole",
        kind="candidate-region",
        description=(
            "Highland terrain near the rim of Nobile crater, another south-polar feature "
            "with adjacent permanently shadowed terrain and irregular high ground."
        ),
        why_interesting=(
            "Adds geographic diversity to comparisons between the near-pole clusters."
        ),
        coordinate_confidence="approximate (rim region, ±10 km)",
        source_note="IAU Gazetteer region centroid. Not a certified landing site.",
        color="#60a5fa",
    ),
)

SITE_BY_ID = {site.id: site for site in CANDIDATE_SITES}


def get_site(site_id: str) -> CandidateSite | None:
    return SITE_BY_ID.get(site_id)


def list_sites() -> list[dict]:
    return [site.to_dict() for site in CANDIDATE_SITES]
