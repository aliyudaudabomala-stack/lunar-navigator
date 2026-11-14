"""Grid scan around Nobile to pick a sunlit rim demonstration point."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.analysis_service import analyze

WHEN = datetime(2026, 11, 24, 12, tzinfo=timezone.utc)

best = []
for lat in [-85.2, -85.6, -86.0, -86.4, -86.8, -87.2]:
    for lon in [30, 40, 50, 60, 70, 80]:
        result = analyze(lat=lat, lon=lon, when=WHEN, window_days=7, step_minutes=60)
        terrain = result["terrain"]
        best.append(
            (
                result["assessment"]["score"],
                lat,
                lon,
                terrain["elevation_m"],
                terrain["slope_deg"],
                result["illumination"]["sun_visible_fraction"],
                result["comms"]["earth_visible_fraction"],
            )
        )

for row in sorted(best, reverse=True)[:12]:
    print(
        f"score={row[0]:5.1f} lat={row[1]:.1f} lon={row[2]:5.1f} "
        f"elev={row[3]!s:>7} slope={row[4]!s:>5} sun={row[5]:.2f} earth={row[6]:.2f}"
    )
