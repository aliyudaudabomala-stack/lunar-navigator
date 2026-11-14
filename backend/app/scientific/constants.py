"""Physical and astronomical constants used across the scientific core.

Values are annotated with their source so that downstream documentation and
the UI can show exactly which reference frame/constant is in play.
"""

from __future__ import annotations

import math

# --- Time -------------------------------------------------------------------
#: Difference TT - UTC in seconds for the epoch of this prototype.
#: TAI-UTC = 37 s (no leap second has been introduced since 2017-01-01) and
#: TT = TAI + 32.184 s, therefore TT-UTC = 69.184 s. Documented in
#: docs/scientific-methodology.md.
TT_MINUS_UTC_SECONDS = 69.184

#: Julian Date of the J2000.0 epoch (2000-01-01 12:00 TT).
JD_J2000 = 2451545.0

#: Days per Julian century.
DAYS_PER_CENTURY = 36525.0

# --- Moon -------------------------------------------------------------------
#: LOLA reference sphere radius, metres. This is the OFFSET of the LOLA GDR
#: polar DEM products and is also the radius used for spherical geometry here.
MOON_RADIUS_M = 1_737_400.0
MOON_RADIUS_KM = MOON_RADIUS_M / 1000.0

#: IAU 2015 (WGCCRE) rotational elements for the Moon, T in Julian centuries
#: and d in days from J2000 TT. Periodic (physical libration) terms are omitted;
#: their amplitude is < 0.04 deg, far below the 240 m DEM horizon resolution.
MOON_POLE_RA_DEG = (269.9949, 0.0031)
MOON_POLE_DEC_DEG = (66.5392, 0.0130)
MOON_PRIME_MERIDIAN_DEG = (38.3213, 13.17635815, -1.4e-12)

#: Mean lunar obliquity to the ecliptic (deg) — used only for sanity checks.
MOON_OBLIQUITY_TO_ECLIPTIC_DEG = 1.5424

#: Mean synodic month (days) — used for UI copy / education only.
SYNODIC_MONTH_DAYS = 29.530588853

# --- Sun --------------------------------------------------------------------
#: Astronomical unit in km (IAU 2012).
AU_KM = 149_597_870.7
#: Solar angular radius at 1 AU (deg) — used for geometric limb tests.
SUN_ANGULAR_RADIUS_DEG = 0.2666

# --- Earth ------------------------------------------------------------------
#: Mean Earth radius (km), IUGG.
EARTH_RADIUS_KM = 6371.0084
#: Earth's equatorial radius (km).
EARTH_EQUATORIAL_RADIUS_KM = 6378.137
#: Earth's mean angular radius seen from the Moon at mean distance (deg).
EARTH_MEAN_ANGULAR_RADIUS_DEG = 0.952

# --- Math helpers -----------------------------------------------------------
DEG = math.pi / 180.0
ARCSEC = DEG / 3600.0

__all__ = [
    "TT_MINUS_UTC_SECONDS",
    "JD_J2000",
    "DAYS_PER_CENTURY",
    "MOON_RADIUS_M",
    "MOON_RADIUS_KM",
    "MOON_POLE_RA_DEG",
    "MOON_POLE_DEC_DEG",
    "MOON_PRIME_MERIDIAN_DEG",
    "MOON_OBLIQUITY_TO_ECLIPTIC_DEG",
    "SYNODIC_MONTH_DAYS",
    "AU_KM",
    "SUN_ANGULAR_RADIUS_DEG",
    "EARTH_RADIUS_KM",
    "EARTH_EQUATORIAL_RADIUS_KM",
    "EARTH_MEAN_ANGULAR_RADIUS_DEG",
    "DEG",
    "ARCSEC",
]
