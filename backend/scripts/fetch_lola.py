"""Download the real NASA LOLA south-polar DEM used by Lunar Navigator.

Usage (from the backend directory):

    .\\.venv\\Scripts\\python.exe scripts\\fetch_lola.py

The product is a static NASA PDS archive file (~29 MB). The application never
downloads it at request time; this script is the explicit, auditable install
step. If the download is unavailable, the backend automatically falls back to a
clearly-labelled illustrative terrain model.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

BASE = (
    "https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/"
    "lrolol_1xxx/data/lola_gdr/polar/img"
)
IMAGE = "ldem_75s_240m.img"
LABEL = "ldem_75s_240m.lbl"
#: 3812 × 3812 pixels × int16 little-endian.
EXPECTED_BYTES = 3812 * 3812 * 2


def fetch(client: httpx.Client, filename: str, destination: Path) -> None:
    url = f"{BASE}/{filename}"
    print(f"GET {url}")
    with client.stream("GET", url) as response:
        response.raise_for_status()
        total = int(response.headers.get("content-length", 0))
        destination.parent.mkdir(parents=True, exist_ok=True)
        partial = destination.with_suffix(destination.suffix + ".part")
        written = 0
        with partial.open("wb") as handle:
            for chunk in response.iter_bytes(1024 * 256):
                handle.write(chunk)
                written += len(chunk)
                if total:
                    pct = written * 100.0 / total
                    print(f"\r  {written:,} / {total:,} bytes ({pct:5.1f}%)", end="")
        print()
        partial.replace(destination)


def sha256(path: Path, limit: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        remaining = limit
        while remaining > 0:
            block = handle.read(min(remaining, 1024 * 1024))
            if not block:
                break
            digest.update(block)
            remaining -= len(block)
    return digest.hexdigest()


def main() -> int:
    data_dir = Path(__file__).resolve().parents[1] / "data" / "lola"
    data_dir.mkdir(parents=True, exist_ok=True)
    image_path = data_dir / IMAGE
    label_path = data_dir / LABEL

    if image_path.exists() and image_path.stat().st_size == EXPECTED_BYTES:
        print(f"Already present: {image_path} ({image_path.stat().st_size:,} bytes)")
    else:
        with httpx.Client(timeout=120.0, follow_redirects=True) as client:
            fetch(client, IMAGE, image_path)
            fetch(client, LABEL, label_path)

    size = image_path.stat().st_size
    if size != EXPECTED_BYTES:
        print(
            f"ERROR: expected {EXPECTED_BYTES:,} bytes but found {size:,}. "
            "The DEM is incomplete; delete it and retry.",
            file=sys.stderr,
        )
        return 1

    retrieved = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    meta = {
        "product_id": "LDEM_75S_240M",
        "dataset_id": "LRO-L-LOLA-4-GDR-V1.0",
        "title": "LRO LOLA gridded topography, 240 m/pixel, south polar stereographic",
        "source": "NASA Planetary Data System (PDS) Geosciences Node",
        "source_url": f"{BASE}/{IMAGE}",
        "label_url": f"{BASE}/{LABEL}",
        "retrieved_at": retrieved,
        "bytes": size,
        "lines": 3812,
        "samples": 3812,
        "resolution_m": 240.0,
        "projection": "south polar stereographic, spherical, true at the pole",
        "reference_radius_m": 1737400.0,
        "vertical_datum": "radius relative to a 1737.4 km reference sphere",
        "coverage": "75S to 90S, full longitude",
        "sha256_prefix_8mib": sha256(image_path),
        "notes": (
            "Downloaded once for this deployment. Static NASA archive product, not a live "
            "instrument feed. SHA-256 covers the first 8 MiB to keep startup cheap."
        ),
    }
    (data_dir / "dem_meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(f"Installed {IMAGE} ({size:,} bytes)")
    print(f"Wrote {data_dir / 'dem_meta.json'}")
    print(f"Label present: {label_path.exists()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
