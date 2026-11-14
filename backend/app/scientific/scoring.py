"""Transparent, priority-weighted mission assessment.

This is a *planning heuristic*. It does not establish landing safety, mission
feasibility, nor hardware performance. Every component score is exposed so a
reviewer can see exactly how the recommendation was produced.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class Priorities:
    power: float = 35.0
    comms: float = 30.0
    terrain: float = 20.0
    timing: float = 15.0

    def normalized(self) -> dict[str, float]:
        raw = {
            "power": max(0.0, self.power),
            "comms": max(0.0, self.comms),
            "terrain": max(0.0, self.terrain),
            "timing": max(0.0, self.timing),
        }
        total = sum(raw.values())
        if total <= 0:
            return {"power": 0.35, "comms": 0.30, "terrain": 0.20, "timing": 0.15}
        return {k: v / total for k, v in raw.items()}


def grade_for(score: float) -> tuple[str, str]:
    if score >= 85:
        return "A", "Excellent relative planning score"
    if score >= 70:
        return "B", "Strong relative planning score"
    if score >= 55:
        return "C", "Moderate relative planning score"
    if score >= 40:
        return "D", "Marginal relative planning score"
    return "E", "Poor relative planning score"


def component_scores(
    *,
    illumination: Mapping,
    comms: Mapping,
    terrain: Mapping,
    landing_sun_margin_deg: float,
    landing_earth_margin_deg: float,
) -> dict:
    """Return 0-100 component scores with the raw inputs used."""

    sun_fraction = float(illumination.get("sun_visible_fraction", 0.0))
    mean_sun_elevation = float(illumination.get("mean_sun_elevation_deg", 0.0))
    elevation_quality = clamp((mean_sun_elevation + 1.0) / 15.0)
    solar_score = 100.0 * (0.80 * sun_fraction + 0.20 * elevation_quality)

    earth_fraction = float(comms.get("earth_visible_fraction", 0.0))
    longest_earth = float(comms.get("longest_earth_window_hours", 0.0))
    continuity = clamp(longest_earth / 24.0)
    comms_score = 100.0 * (0.75 * earth_fraction + 0.25 * continuity)

    slope = terrain.get("slope_deg")
    roughness = terrain.get("roughness_m")
    sky = terrain.get("sky_view_factor")
    has_terrain = terrain.get("source_type") in {"lola-gdr", "illustrative-fallback"}

    if has_terrain and slope is not None:
        slope_score = clamp(1.0 - float(slope) / 25.0)
        rough_score = clamp(1.0 - float(roughness or 0.0) / 250.0)
        sky_score = clamp(float(sky if sky is not None else 0.9))
        terrain_score = 100.0 * (0.45 * slope_score + 0.40 * sky_score + 0.15 * rough_score)
    else:
        slope_score = rough_score = sky_score = 0.5
        terrain_score = 50.0

    light_margin = clamp((landing_sun_margin_deg + 0.5) / 8.0)
    comms_margin = clamp((landing_earth_margin_deg + 0.5) / 6.0)
    timing_score = 100.0 * (0.60 * light_margin + 0.40 * comms_margin)

    return {
        "power": {
            "score": round(solar_score, 1),
            "inputs": {
                "sun_visible_fraction": round(sun_fraction, 4),
                "mean_sun_elevation_deg": round(mean_sun_elevation, 3),
                "elevation_quality": round(elevation_quality, 4),
            },
            "formula": "100 × (0.80 × sunlight_fraction + 0.20 × clamp((mean_sun_elevation + 1)/15))",
        },
        "comms": {
            "score": round(comms_score, 1),
            "inputs": {
                "earth_visible_fraction": round(earth_fraction, 4),
                "longest_earth_window_hours": round(longest_earth, 2),
                "continuity": round(continuity, 4),
            },
            "formula": "100 × (0.75 × earth_visible_fraction + 0.25 × clamp(longest_window/24h))",
        },
        "terrain": {
            "score": round(terrain_score, 1),
            "inputs": {
                "slope_deg": slope,
                "slope_score": round(slope_score, 4),
                "roughness_m": roughness,
                "roughness_score": round(rough_score, 4),
                "sky_view_factor": sky,
                "sky_view_score": round(sky_score, 4),
                "terrain_source": terrain.get("source_type"),
            },
            "formula": "100 × (0.45 × slope + 0.40 × sky-view + 0.15 × roughness)",
        },
        "timing": {
            "score": round(timing_score, 1),
            "inputs": {
                "sun_margin_deg": round(landing_sun_margin_deg, 3),
                "earth_margin_deg": round(landing_earth_margin_deg, 3),
                "light_margin_score": round(light_margin, 4),
                "comms_margin_score": round(comms_margin, 4),
            },
            "formula": "100 × (0.60 × sun-margin + 0.40 × earth-margin)",
        },
    }


def overall_score(components: Mapping, priorities: Priorities) -> float:
    weights = priorities.normalized()
    total = sum(components[key]["score"] * weights[key] for key in weights)
    return round(float(total), 1)


def build_assessment(
    *,
    illumination: Mapping,
    comms: Mapping,
    terrain: Mapping,
    landing_sun_margin_deg: float,
    landing_earth_margin_deg: float,
    priorities: Priorities,
    site_name: str,
    window_days: float,
    window_start: str,
    sun_visible_at_landing: bool,
    earth_visible_at_landing: bool,
    next_sunset_utc: str | None,
) -> dict:
    components = component_scores(
        illumination=illumination,
        comms=comms,
        terrain=terrain,
        landing_sun_margin_deg=landing_sun_margin_deg,
        landing_earth_margin_deg=landing_earth_margin_deg,
    )
    weights = priorities.normalized()
    score = overall_score(components, priorities)
    grade, label = grade_for(score)

    advantages: list[str] = []
    disadvantages: list[str] = []
    risks: list[str] = []

    sun_fraction = float(illumination.get("sun_visible_fraction", 0.0))
    earth_fraction = float(comms.get("earth_visible_fraction", 0.0))
    mean_sun_el = float(illumination.get("mean_sun_elevation_deg", 0.0))
    slope = terrain.get("slope_deg")
    sky = terrain.get("sky_view_factor")

    if sun_fraction >= 0.80:
        advantages.append(
            f"Extended sunlight: {sun_fraction * 100:.0f}% of the {window_days:g}-day window is sunlit."
        )
    if earth_fraction >= 0.50:
        advantages.append(
            f"Direct-to-Earth geometry available {earth_fraction * 100:.0f}% of the window "
            f"(longest continuous window {comms.get('longest_earth_window_hours', 0):.1f} h)."
        )
    if slope is not None and float(slope) <= 5.0:
        advantages.append(f"Relatively gentle local slope ({float(slope):.1f}° at the sampled point).")
    if sky is not None and float(sky) >= 0.90:
        advantages.append("Open sky view: the local terrain horizon is low in most directions.")
    if illumination.get("longest_sun_window_hours", 0) >= 24 * 5:
        advantages.append(
            f"Longest continuous sunlit interval is {illumination['longest_sun_window_hours']:.1f} h."
        )
    if earth_visible_at_landing and sun_visible_at_landing:
        advantages.append("Both sunlight and direct Earth visibility exist at the selected landing instant.")

    if sun_fraction < 0.35:
        disadvantages.append(
            f"Limited sunlight: only {sun_fraction * 100:.0f}% of the window is sunlit; battery sizing dominates."
        )
    if earth_fraction < 0.10:
        disadvantages.append(
            "Direct-to-Earth visibility is rare or absent; a relay architecture or surface antenna "
            "strategy would be required."
        )
    if mean_sun_el < 3.0:
        disadvantages.append(
            f"Low mean solar elevation ({mean_sun_el:.1f}°): grazing light, long shadows and severe thermal gradients."
        )
    if slope is not None and float(slope) > 10.0:
        disadvantages.append(f"Local slope of {float(slope):.1f}° is demanding for lander footpads and deployment.")
    if sky is not None and float(sky) < 0.80:
        disadvantages.append("Terrain blocks a significant part of the sky, reducing both power and comms margins.")
    if not sun_visible_at_landing:
        disadvantages.append("The selected landing instant is in shadow at this site.")
    if not earth_visible_at_landing:
        disadvantages.append("Earth is below the local terrain horizon at the selected landing instant.")

    if mean_sun_el < 1.0 and sun_fraction < 0.5:
        risks.append("Cryogenic temperatures and rapid thermal cycling: heater power must be modelled explicitly.")
    if earth_fraction < 0.05:
        risks.append("No direct-to-Earth link geometry for most of the window — contingency relay planning is critical.")
    if next_sunset_utc:
        risks.append(f"Next local sunset in the sampled window at {next_sunset_utc}; plan the surface timeline around it.")
    if terrain.get("is_illustrative"):
        risks.append("Terrain fallback is illustrative only — no engineering-grade slope or horizon conclusion is possible.")
    elif terrain.get("source_type") == "spherical-fallback":
        risks.append("No terrain DEM covers this point; horizon obstruction and slope are not modelled.")
    if float(terrain.get("roughness_m") or 0.0) > 150:
        risks.append(
            f"High local roughness ({float(terrain.get('roughness_m')):.0f} m std-dev at 240 m scale) "
            "may affect touchdown and mobility."
        )
    if illumination.get("sample_count", 0) and illumination.get("step_minutes", 10) > 20:
        risks.append("Timeline resolution is coarse; window edges are approximate.")
    if not risks:
        risks.append("No dominant geometry risk was flagged by the heuristic — this is not a safety certification.")

    priority_summary = ", ".join(
        f"{key} {weights[key] * 100:.0f}%" for key in ("power", "comms", "terrain", "timing")
    )
    top_component = max(components, key=lambda k: components[k]["score"] * weights[k])
    weak_component = min(components, key=lambda k: components[k]["score"] * weights[k])

    explanation = (
        f"{site_name} scores {score:.1f}/100 for the priorities {priority_summary}. "
        f"The strongest weighted contribution is {top_component} "
        f"({components[top_component]['score']:.0f}/100); the weakest is {weak_component} "
        f"({components[weak_component]['score']:.0f}/100). "
        f"Over {window_days:g} days starting {window_start}, the site is sunlit "
        f"{sun_fraction * 100:.0f}% of the time and has direct Earth geometry "
        f"{earth_fraction * 100:.0f}% of the time. "
        "Scores are relative planning indicators, not landing-safety or mission-feasibility determinations."
    )

    return {
        "score": score,
        "grade": grade,
        "label": label,
        "components": components,
        "weights": {k: round(v, 4) for k, v in weights.items()},
        "advantages": advantages,
        "disadvantages": disadvantages,
        "risks": risks,
        "explanation": explanation,
        "disclaimer": (
            "This heuristic combines illumination, direct-to-Earth geometry, terrain proxies and "
            "landing-time conditions. It is not a certified landing-site safety assessment, does not "
            "model the lander, and must not be used as the sole basis for mission decisions."
        ),
    }
