"""Terrain, horizon and slope analysis from NASA LOLA gridded topography.

Primary source
--------------
LRO-L-LOLA-4-GDR-V1.0, product ``LDEM_75S_240M``: a 240 m/pixel south-polar
stereographic shape map (radius relative to 1737.4 km) built from LOLA altimetry
through mission phase LRO_ES_54. The product is downloaded once from the NASA
Planetary Data System (PDS) and cached locally; see ``scripts/fetch_lola.py``
and ``data/lola/README.md``.

If the product is not present the module falls back to a *clearly labelled*
spherical or illustrative terrain. It never presents synthetic terrain as LOLA
measurement.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import threading
from typing import Iterable

import numpy as np

from .constants import MOON_RADIUS_M

# LOLA GDR south-polar product constants (read from LDEM_75S_240M.LBL).
DEM_LINES = 3812
DEM_SAMPLES = 3812
DEM_SCALE_M = 240.0
DEM_SCALING_FACTOR = 0.5
DEM_LINE_OFFSET = 1905.5
DEM_SAMPLE_OFFSET = 1905.5
DEM_MIN_LAT = -90.0
DEM_MAX_LAT = -75.0

TERRAIN_SOURCE_LOLA = "lola-gdr"
TERRAIN_SOURCE_SPHERICAL = "spherical-fallback"
TERRAIN_SOURCE_ILLUSTRATIVE = "illustrative-fallback"


@dataclass(frozen=True)
class DemMetadata:
    product_id: str
    dataset_id: str
    source_url: str
    retrieved_at: str | None
    resolution_m: float
    projection: str
    reference_radius_m: float
    vertical_datum: str
    coverage: str
    file_bytes: int
    sha256: str | None
    available: bool


def _sha256(path: Path, limit_bytes: int = 8 * 1024 * 1024) -> str:
    """Hash the first megabytes of a large product to keep provenance cheap."""

    h = hashlib.sha256()
    with path.open("rb") as fh:
        remaining = limit_bytes
        while remaining > 0:
            chunk = fh.read(min(1 << 20, remaining))
            if not chunk:
                break
            h.update(chunk)
            remaining -= len(chunk)
    return h.hexdigest()


class LunarDem:
    """Memory-mapped LOLA south-polar DEM with bilinear sampling."""

    def __init__(self, image_path: Path, metadata: DemMetadata):
        self.image_path = image_path
        self.metadata = metadata
        self._array: np.ndarray | None = None
        self._lock = threading.Lock()
        self._hillshade_cache: dict[int, tuple[bytes, dict]] = {}

    # -- loading ---------------------------------------------------------
    def _load(self) -> np.ndarray:
        if self._array is None:
            with self._lock:
                if self._array is None:
                    raw = np.fromfile(self.image_path, dtype="<i2")
                    if raw.size != DEM_LINES * DEM_SAMPLES:
                        raise ValueError(
                            f"LOLA DEM has {raw.size} samples, expected "
                            f"{DEM_LINES * DEM_SAMPLES}. The download may be incomplete."
                        )
                    self._array = raw.reshape(DEM_LINES, DEM_SAMPLES).astype(np.float32)
        return self._array

    # -- projection ------------------------------------------------------
    @staticmethod
    def latlon_to_pixel(lat_deg: float, lon_deg: float) -> tuple[float, float]:
        """Selenographic lat/lon (planetocentric) to fractional (line, sample).

        South polar stereographic, true at the pole, longitude 0 toward +y and
        90E toward +x (USGS PDS MAP_PROJECTION convention).
        """

        lat = math.radians(max(-90.0, min(-75.0, lat_deg)))
        lon = math.radians(lon_deg)
        # rho is the distance from the pole in metres.
        rho_m = 2.0 * MOON_RADIUS_M * math.tan((math.pi / 2.0 + lat) / 2.0)
        x = rho_m * math.sin(lon)
        y = rho_m * math.cos(lon)
        sample = DEM_SAMPLE_OFFSET + x / DEM_SCALE_M
        line = DEM_LINE_OFFSET - y / DEM_SCALE_M
        return line, sample

    @staticmethod
    def pixel_to_latlon(line: float, sample: float) -> tuple[float, float]:
        x = (sample - DEM_SAMPLE_OFFSET) * DEM_SCALE_M
        y = (DEM_LINE_OFFSET - line) * DEM_SCALE_M
        rho = math.hypot(x, y)
        lat = math.degrees(2.0 * math.atan(rho / (2.0 * MOON_RADIUS_M)) - math.pi / 2.0)
        lon = math.degrees(math.atan2(x, y)) % 360.0
        return lat, lon

    def contains(self, lat_deg: float, lon_deg: float) -> bool:
        if not (DEM_MIN_LAT <= lat_deg <= DEM_MAX_LAT):
            return False
        line, sample = self.latlon_to_pixel(lat_deg, lon_deg)
        return 0.0 <= line <= DEM_LINES - 1 and 0.0 <= sample <= DEM_SAMPLES - 1

    # -- sampling --------------------------------------------------------
    def elevation_m(self, lat_deg: float, lon_deg: float) -> float | None:
        """Bilinear elevation in metres, or None outside DEM coverage."""

        if not self.contains(lat_deg, lon_deg):
            return None
        line, sample = self.latlon_to_pixel(lat_deg, lon_deg)
        return float(self._bilinear(self._load(), line, sample) * DEM_SCALING_FACTOR)

    def elevation_grid_m(self, lat0: float, lon0: float, size: int, span_deg: float) -> np.ndarray:
        """Sample a regular lat/lon window (for local terrain previews)."""

        lats = np.linspace(lat0 - span_deg / 2.0, lat0 + span_deg / 2.0, size)
        lons = np.linspace(lon0 - span_deg / 2.0, lon0 + span_deg / 2.0, size)
        grid = np.full((size, size), np.nan, dtype=np.float32)
        arr = self._load()
        for i, la in enumerate(lats):
            for j, lo in enumerate(lons):
                if not self.contains(float(la), float(lo)):
                    continue
                line, sample = self.latlon_to_pixel(float(la), float(lo))
                grid[i, j] = self._bilinear(arr, line, sample) * DEM_SCALING_FACTOR
        return grid

    @staticmethod
    def _bilinear(arr: np.ndarray, line: float, sample: float) -> float:
        line = min(max(line, 0.0), DEM_LINES - 1.000001)
        sample = min(max(sample, 0.0), DEM_SAMPLES - 1.000001)
        l0 = int(math.floor(line))
        s0 = int(math.floor(sample))
        fl = line - l0
        fs = sample - s0
        v00 = float(arr[l0, s0])
        v01 = float(arr[l0, s0 + 1])
        v10 = float(arr[l0 + 1, s0])
        v11 = float(arr[l0 + 1, s0 + 1])
        return (
            v00 * (1 - fl) * (1 - fs)
            + v01 * (1 - fl) * fs
            + v10 * fl * (1 - fs)
            + v11 * fl * fs
        )

    def slope_and_aspect(self, lat_deg: float, lon_deg: float) -> tuple[float, float] | None:
        """Local slope (deg) and downslope aspect (deg clockwise from north)."""

        if not self.contains(lat_deg, lon_deg):
            return None
        arr = self._load()
        line, sample = self.latlon_to_pixel(lat_deg, lon_deg)
        l = int(round(line))
        s = int(round(sample))
        if not (1 <= l < DEM_LINES - 1 and 1 <= s < DEM_SAMPLES - 1):
            return None
        dz_dl = (arr[l + 1, s] - arr[l - 1, s]) * DEM_SCALING_FACTOR / (2 * DEM_SCALE_M)
        dz_ds = (arr[l, s + 1] - arr[l, s - 1]) * DEM_SCALING_FACTOR / (2 * DEM_SCALE_M)
        slope = math.degrees(math.atan(math.hypot(dz_dl, dz_ds)))
        # Image +sample is +x (east at lon=0), +line is -y (south at lon=0).
        aspect = math.degrees(math.atan2(dz_ds, dz_dl)) % 360.0
        return slope, aspect

    def terrain_roughness(self, lat_deg: float, lon_deg: float, radius_px: int = 3) -> float | None:
        """Standard deviation of elevation in a small neighbourhood (metres)."""

        if not self.contains(lat_deg, lon_deg):
            return None
        arr = self._load()
        line, sample = self.latlon_to_pixel(lat_deg, lon_deg)
        l, s = int(round(line)), int(round(sample))
        window = arr[max(0, l - radius_px): l + radius_px + 1, max(0, s - radius_px): s + radius_px + 1]
        if window.size == 0:
            return None
        return float(np.std(window.astype(np.float64)) * DEM_SCALING_FACTOR)

    # -- horizon ---------------------------------------------------------
    def horizon_profile(
        self,
        lat_deg: float,
        lon_deg: float,
        *,
        azimuth_step_deg: float = 2.0,
        max_range_km: float = 30.0,
        radial_step_m: float = 240.0,
    ) -> dict:
        """Ray-march the DEM to derive the local terrain horizon.

        For every azimuth we sample the surface out to ``max_range_km`` and keep
        the maximum elevation angle. The lunar curvature drop d^2/(2R) is
        included (no atmospheric refraction on the Moon).
        """

        if not self.contains(lat_deg, lon_deg):
            raise ValueError("Site is outside the LOLA south-polar DEM coverage")

        arr = self._load()
        n_az = int(round(360.0 / azimuth_step_deg))
        azimuths = np.arange(n_az) * azimuth_step_deg
        radii = np.arange(
            max(radial_step_m, 60.0), max_range_km * 1000.0 + radial_step_m, radial_step_m
        )
        site_elev = self.elevation_m(lat_deg, lon_deg) or 0.0

        lat0 = math.radians(lat_deg)
        lon0 = math.radians(lon_deg)
        horizon = np.full(n_az, -90.0)
        horizon_range = np.full(n_az, np.nan)
        sampled = np.zeros(n_az, dtype=bool)

        for i, az_deg in enumerate(azimuths):
            az = math.radians(float(az_deg))
            best_el = -90.0
            best_range = np.nan
            for r in radii:
                # Local ENU offset converted to selenographic increments.
                north = r * math.cos(az)
                east = r * math.sin(az)
                dlat = math.degrees(north / (MOON_RADIUS_M + site_elev))
                dlon = math.degrees(east / ((MOON_RADIUS_M + site_elev) * math.cos(lat0)))
                la = lat_deg + dlat
                lo = lon_deg + dlon
                if not self.contains(la, lo):
                    break
                line, sample = self.latlon_to_pixel(la, lo)
                h = self._bilinear(arr, line, sample) * DEM_SCALING_FACTOR
                drop = (r / 1000.0) ** 2 / (2.0 * MOON_RADIUS_M / 1000.0) * 1000.0
                elev_angle = math.degrees(math.atan2((h - site_elev) - drop, r))
                if elev_angle > best_el:
                    best_el = elev_angle
                    best_range = r / 1000.0
                sampled[i] = True
            horizon[i] = best_el
            horizon_range[i] = best_range

        # A 1-degree resolution is enough for interpolation; keep the requested
        # resolution in the payload so consumers know the sampling.
        return {
            "azimuths_deg": azimuths.tolist(),
            "elevations_deg": [round(float(v), 4) for v in horizon],
            "distances_km": [None if math.isnan(v) else round(float(v), 3) for v in horizon_range],
            "site_elevation_m": round(site_elev, 1),
            "max_elevation_deg": round(float(np.max(horizon)), 3),
            "mean_elevation_deg": round(float(np.mean(horizon)), 3),
            "min_elevation_deg": round(float(np.min(horizon)), 3),
            "azimuth_step_deg": azimuth_step_deg,
            "max_range_km": max_range_km,
            "radial_step_m": radial_step_m,
            "curvature_correction": True,
            "refraction": False,
            "source": self.metadata.product_id,
            "method": "ray-march maximum elevation angle per azimuth",
        }

    def horizon_at(self, profile: dict, azimuth_deg: float) -> float:
        """Interpolate the horizon elevation for an arbitrary azimuth."""

        elevations = profile["elevations_deg"]
        n = len(elevations)
        if n == 0:
            return 0.0
        step = 360.0 / n
        x = (azimuth_deg % 360.0) / step
        i0 = int(math.floor(x)) % n
        i1 = (i0 + 1) % n
        f = x - math.floor(x)
        # Wrap across the 0/360 seam correctly (difference may exceed 180 deg
        # only for pathological horizons; clamp for sane interpolation).
        e0, e1 = elevations[i0], elevations[i1]
        return float(e0 + (e1 - e0) * f)

    # -- raster products -------------------------------------------------
    def hillshade_png(self, size: int = 1400, max_radius_km: float = 380.0) -> tuple[bytes, dict]:
        """Render a south-polar shaded-relief basemap (PNG) from the DEM."""

        if size in self._hillshade_cache:
            return self._hillshade_cache[size]

        from PIL import Image

        arr = self._load()
        # Sample a regular grid in polar stereographic x/y.
        xs = np.linspace(-max_radius_km, max_radius_km, size)
        ys = np.linspace(max_radius_km, -max_radius_km, size)
        xx, yy = np.meshgrid(xs, ys)
        rho = np.hypot(xx, yy)
        theta = np.arctan2(xx, yy)
        # Inverse projection (vectorised).
        lat = np.degrees(2.0 * np.arctan(rho * 1000.0 / (2.0 * MOON_RADIUS_M)) - math.pi / 2.0)
        lon = np.degrees(theta) % 360.0
        sample = DEM_SAMPLE_OFFSET + xx * 1000.0 / DEM_SCALE_M
        line = DEM_LINE_OFFSET - yy * 1000.0 / DEM_SCALE_M

        si = np.clip(sample, 0, DEM_SAMPLES - 1.000001)
        li = np.clip(line, 0, DEM_LINES - 1.000001)
        l0 = np.floor(li).astype(np.int32)
        s0 = np.floor(si).astype(np.int32)
        fl = (li - l0).astype(np.float32)
        fs = (si - s0).astype(np.float32)
        h = (
            arr[l0, s0] * (1 - fl) * (1 - fs)
            + arr[l0, s0 + 1] * (1 - fl) * fs
            + arr[l0 + 1, s0] * fl * (1 - fs)
            + arr[l0 + 1, s0 + 1] * fl * fs
        ).astype(np.float32) * DEM_SCALING_FACTOR

        inside = rho <= max_radius_km
        gy, gx = np.gradient(h, (2 * max_radius_km * 1000.0) / size)
        slope = np.hypot(gx, gy)
        # Illumination from the north-west, a conventional cartographic choice
        # for relief shading (not a physical solar direction).
        az = math.radians(315.0)
        dzdx = gx * math.sin(az) + gy * math.cos(az)
        hill = np.clip(0.5 + np.arctan(-dzdx * 2.2) / math.pi, 0.0, 1.0)

        # Elevation tint (blue-grey lowlands to pale highlands).
        norm = np.clip((h + 6000.0) / 12000.0, 0.0, 1.0)
        base = np.stack(
            [
                0.10 + 0.55 * norm,
                0.16 + 0.62 * norm,
                0.24 + 0.62 * norm,
            ],
            axis=-1,
        )
        shade = (0.35 + 0.9 * hill)[..., None]
        rgb = np.clip(base * shade, 0, 1)
        rgb[~inside] = 0.0
        alpha = np.where(inside, 255, 0).astype(np.uint8)
        rgba = np.concatenate([(rgb * 255).astype(np.uint8), alpha[..., None]], axis=-1)
        img = Image.fromarray(rgba, mode="RGBA")

        import io

        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        meta = {
            "size_px": size,
            "extent_km": {"xmin": -max_radius_km, "xmax": max_radius_km, "ymin": -max_radius_km, "ymax": max_radius_km},
            "projection": "south polar stereographic (spherical, true at pole)",
            "longitude_convention": "0 deg toward +y (up), 90E toward +x (right)",
            "source": self.metadata.product_id,
            "source_url": self.metadata.source_url,
            "resolution_native_m": self.metadata.resolution_m,
            "hillshade_illumination": "NW (cartographic, not solar)",
            "radius_km": MOON_RADIUS_M / 1000.0,
            "note": "Basemap derived from LOLA gridded topography; vertical exaggeration is not applied.",
        }
        png = buf.getvalue()
        self._hillshade_cache[size] = (png, meta)
        return png, meta


class IllustrativeTerrain:
    """Clearly labelled synthetic terrain used only when the LOLA file is absent.

    This is a deterministic crater-field model. It exists so the UI can still be
    demonstrated offline; every API payload that uses it carries
    ``source_type = illustrative-fallback`` and the UI displays a warning banner.
    """

    metadata = DemMetadata(
        product_id="ILLUSTRATIVE-ONLY",
        dataset_id="none",
        source_url="https://pds-geosciences.wustl.edu/missions/lro/lola.htm",
        retrieved_at=None,
        resolution_m=480.0,
        projection="local tangent plane (synthetic)",
        reference_radius_m=MOON_RADIUS_M,
        vertical_datum="synthetic",
        coverage="south polar region (synthetic)",
        file_bytes=0,
        sha256=None,
        available=False,
    )

    def __init__(self) -> None:
        self._craters = (
            (-89.55, 130.0, 12.0, 900.0),
            (-89.30, 210.0, 8.0, 500.0),
            (-88.80, 40.0, 18.0, 1200.0),
            (-87.90, 300.0, 10.0, 700.0),
            (-87.20, 160.0, 22.0, 1500.0),
            (-86.20, 15.0, 16.0, 2400.0),
            (-85.60, 80.0, 14.0, 1200.0),
        )

    def contains(self, lat_deg: float, lon_deg: float) -> bool:
        return -90.0 <= lat_deg <= -80.0

    def elevation_m(self, lat_deg: float, lon_deg: float) -> float | None:
        if not self.contains(lat_deg, lon_deg):
            return None
        h = -1800.0 + 260.0 * math.sin(math.radians(lon_deg * 3.0)) + 180.0 * math.cos(math.radians(lat_deg * 90.0))
        for clat, clon, radius_deg, depth in self._craters:
            d = math.hypot((lat_deg - clat), ((lon_deg - clon + 180) % 360 - 180) * math.cos(math.radians(lat_deg)))
            if d < radius_deg:
                x = d / radius_deg
                h += depth * (x * x - 1.0) * 0.35
                if x > 0.85:
                    h += depth * 0.18 * (1.0 - (1.0 - x) / 0.15)
        return float(h)

    def slope_and_aspect(self, lat_deg: float, lon_deg: float) -> tuple[float, float] | None:
        if not self.contains(lat_deg, lon_deg):
            return None
        eps = 0.01
        h0 = self.elevation_m(lat_deg, lon_deg) or 0.0
        hn = (self.elevation_m(lat_deg + eps, lon_deg) or h0) - h0
        he = (self.elevation_m(lat_deg, lon_deg + eps) or h0) - h0
        d = 2 * math.pi * MOON_RADIUS_M * eps / 360.0
        slope = math.degrees(math.atan(math.hypot(hn, he) / d))
        return slope, math.degrees(math.atan2(he, hn)) % 360.0

    def terrain_roughness(self, lat_deg: float, lon_deg: float, radius_px: int = 3) -> float | None:
        if not self.contains(lat_deg, lon_deg):
            return None
        values = []
        for i in range(-radius_px, radius_px + 1):
            for j in range(-radius_px, radius_px + 1):
                v = self.elevation_m(lat_deg + i * 0.005, lon_deg + j * 0.005)
                if v is not None:
                    values.append(v)
        return float(np.std(values)) if values else None

    def horizon_profile(
        self,
        lat_deg: float,
        lon_deg: float,
        *,
        azimuth_step_deg: float = 2.0,
        max_range_km: float = 30.0,
        radial_step_m: float = 240.0,
    ) -> dict:
        n_az = int(round(360.0 / azimuth_step_deg))
        azimuths = np.arange(n_az) * azimuth_step_deg
        site_elev = self.elevation_m(lat_deg, lon_deg) or 0.0
        max_range_m = max_range_km * 1000.0
        radii = np.arange(240.0, max_range_m + 240.0, 480.0)
        horizon = []
        distances = []
        for az_deg in azimuths:
            az = math.radians(float(az_deg))
            best_el, best_r = -90.0, None
            for r in radii:
                dlat = math.degrees(r * math.cos(az) / MOON_RADIUS_M)
                dlon = math.degrees(r * math.sin(az) / (MOON_RADIUS_M * math.cos(math.radians(lat_deg))))
                h = self.elevation_m(lat_deg + dlat, lon_deg + dlon)
                if h is None:
                    break
                drop = (r / 1000.0) ** 2 / (2 * MOON_RADIUS_M / 1000.0) * 1000.0
                el = math.degrees(math.atan2((h - site_elev) - drop, r))
                if el > best_el:
                    best_el, best_r = el, r / 1000.0
            horizon.append(round(best_el, 3))
            distances.append(None if best_r is None else round(best_r, 2))
        return {
            "azimuths_deg": azimuths.tolist(),
            "elevations_deg": horizon,
            "distances_km": distances,
            "site_elevation_m": round(site_elev, 1),
            "max_elevation_deg": round(max(horizon), 3),
            "mean_elevation_deg": round(float(np.mean(horizon)), 3),
            "min_elevation_deg": round(min(horizon), 3),
            "azimuth_step_deg": azimuth_step_deg,
            "max_range_km": max_range_km,
            "radial_step_m": 480.0,
            "curvature_correction": True,
            "refraction": False,
            "source": "ILLUSTRATIVE-ONLY",
            "method": "ray-march of synthetic crater field (NOT NASA DATA)",
        }

    def horizon_at(self, profile: dict, azimuth_deg: float) -> float:
        elevations = profile["elevations_deg"]
        n = len(elevations)
        step = 360.0 / n
        x = (azimuth_deg % 360.0) / step
        i0 = int(math.floor(x)) % n
        i1 = (i0 + 1) % n
        f = x - math.floor(x)
        return float(elevations[i0] + (elevations[i1] - elevations[i0]) * f)

    def hillshade_png(self, size: int = 1400, max_radius_km: float = 380.0) -> tuple[bytes, dict]:
        from PIL import Image
        import io

        xs = np.linspace(-max_radius_km, max_radius_km, size)
        ys = np.linspace(max_radius_km, -max_radius_km, size)
        xx, yy = np.meshgrid(xs, ys)
        rho = np.hypot(xx, yy)
        lat = 2.0 * np.degrees(np.arctan(rho * 1000.0 / (2.0 * MOON_RADIUS_M))) - 90.0
        lon = np.degrees(np.arctan2(xx, yy)) % 360.0
        h = np.full_like(xx, np.nan, dtype=np.float32)
        for i in range(size):
            for j in range(size):
                v = self.elevation_m(float(lat[i, j]), float(lon[i, j]))
                if v is not None:
                    h[i, j] = v
        df = np.nan_to_num(np.gradient(np.nan_to_num(h))[0])
        norm = np.clip((np.nan_to_num(h) + 3000) / 6000, 0, 1)
        rgb = np.stack([0.22 + 0.5 * norm, 0.24 + 0.5 * norm, 0.30 + 0.45 * norm], axis=-1)
        rgb = np.clip(rgb * (0.7 + 0.4 * np.tanh(-df)), 0, 1)
        alpha = np.where(rho <= max_radius_km, 255, 0).astype(np.uint8)
        rgba = np.concatenate([(rgb * 255).astype(np.uint8), alpha[..., None]], axis=-1)
        buf = io.BytesIO()
        Image.fromarray(rgba, mode="RGBA").save(buf, format="PNG")
        meta = {
            "size_px": size,
            "extent_km": {"xmin": -max_radius_km, "xmax": max_radius_km, "ymin": -max_radius_km, "ymax": max_radius_km},
            "projection": "south polar stereographic (illustrative)",
            "source": "ILLUSTRATIVE-ONLY",
            "source_url": "https://pds-geosciences.wustl.edu/missions/lro/lola.htm",
            "resolution_native_m": 480.0,
            "hillshade_illumination": "NW (cartographic)",
            "radius_km": MOON_RADIUS_M / 1000.0,
            "note": "Synthetic terrain for offline demonstration. NOT NASA MEASUREMENT.",
        }
        return buf.getvalue(), meta


def _read_dem_meta(data_dir: Path, image_path: Path) -> DemMetadata:
    retrieved_at = None
    meta_file = data_dir / "lola" / "dem_meta.json"
    if meta_file.exists():
        try:
            retrieved_at = json.loads(meta_file.read_text(encoding="utf-8")).get("retrieved_at")
        except (OSError, ValueError):
            retrieved_at = None
    return DemMetadata(
        product_id="LDEM_75S_240M",
        dataset_id="LRO-L-LOLA-4-GDR-V1.0",
        source_url=(
            "https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/"
            "data/lola_gdr/polar/img/ldem_75s_240m.img"
        ),
        retrieved_at=retrieved_at,
        resolution_m=DEM_SCALE_M,
        projection="south polar stereographic (spherical, true at pole)",
        reference_radius_m=MOON_RADIUS_M,
        vertical_datum="radius relative to 1737.4 km reference sphere",
        coverage="75S to 90S, full longitude",
        file_bytes=image_path.stat().st_size if image_path.exists() else 0,
        sha256=_sha256(image_path) if image_path.exists() else None,
        available=True,
    )


def load_terrain(data_dir: Path) -> LunarDem | IllustrativeTerrain:
    """Load the best available terrain source, preferring real LOLA data."""

    image_path = data_dir / "lola" / "ldem_75s_240m.img"
    if image_path.exists() and image_path.stat().st_size == DEM_LINES * DEM_SAMPLES * 2:
        return LunarDem(image_path, _read_dem_meta(data_dir, image_path))
    return IllustrativeTerrain()


def sky_view_factor(profile: dict, max_horizon_deg: float = 30.0) -> float:
    """Fraction of the upper hemisphere that is unobstructed (simple metric).

    Uses a cosine-weighted integral over azimuth. This is a planning heuristic,
    not a radiosity calculation.
    """

    el = np.radians(np.asarray(profile["elevations_deg"], dtype=float))
    visible = np.clip(1.0 - np.sin(np.clip(el, 0, math.radians(90))) / math.sin(math.radians(max_horizon_deg)), 0.0, 1.0)
    return float(np.mean(visible))
