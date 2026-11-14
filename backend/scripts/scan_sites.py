"""Ad-hoc scan used while calibrating the candidate-site catalogue."""

from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.analysis_service import analyze

WHEN = datetime(2026, 11, 24, 12, tzinfo=timezone.utc)
POINTS = [
    ("Shackleton A", -89.295, 129.6),
    ("Shackleton B", -89.32, 129.2),
    ("deGerlache A", -89.0, 263.8),
    ("deGerlache B", -88.5, 267.1),
    ("Connecting", -89.45, 222.7),
    ("Malapert", -86.0, 2.9),
    ("Nobile", -85.28, 53.3),
    ("Cabeus", -85.33, 317.87),
]

for name, lat, lon in POINTS:
    started = time.time()
    result = analyze(lat=lat, lon=lon, when=WHEN, window_days=7, step_minutes=30)
    terrain = result["terrain"]
    print(
        f"{name:14s} elev={terrain['elevation_m']!s:>7} "
        f"slope={terrain['slope_deg']!s:>6} "
        f"sun={result['illumination']['sun_visible_fraction']:.3f} "
        f"earth={result['comms']['earth_visible_fraction']:.3f} "
        f"maxH={result['horizon']['profile']['max_elevation_deg']:.2f} "
        f"swf={terrain['sky_view_factor']} "
        f"score={result['assessment']['score']:.1f} "
        f"t={time.time() - started:.1f}s"
    )
