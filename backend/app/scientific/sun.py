"""Geocentric solar position (Meeus, *Astronomical Algorithms*, ch. 25).

The algorithm returns an apparent geocentric position accurate to roughly
0.01 deg over 1900-2100, which is far below the angular size of the Sun
(~0.53 deg) and the terrain-horizon uncertainty of the 240 m LOLA DEM.

All vectors are unit vectors in the J2000/ICRF equatorial frame once
``to_j2000`` is applied. Times must be supplied in TT as a Julian Date.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

from .constants import AU_KM
from .frames import equatorial_from_ecliptic, precess_equatorial_date_to_j2000
from .time import julian_centuries_tt


@dataclass(frozen=True)
class SolarPosition:
    """Geocentric apparent solar position."""

    ecliptic_longitude_deg: float
    ecliptic_latitude_deg: float
    distance_au: float
    distance_km: float
    right_ascension_deg: float
    declination_deg: float
    #: Unit vector (J2000 equatorial) pointing from the Earth/Moon system
    #: toward the Sun. Parallax between Earth and Moon is handled later.
    unit_vector_j2000: tuple[float, float, float]


def sun_geocentric(jd_tt: float) -> SolarPosition:
    """Compute the apparent geocentric position of the Sun."""

    t = julian_centuries_tt(jd_tt)

    # Geometric mean longitude and mean anomaly (Meeus 25.2, 25.3).
    l0 = 280.46646 + 36000.76983 * t + 0.0003032 * t * t
    m = 357.52911 + 35999.05029 * t - 0.0001537 * t * t
    m_rad = math.radians(m % 360.0)

    # Equation of the centre (Meeus 25.4).
    c = (
        (1.914602 - 0.004817 * t - 0.000014 * t * t) * math.sin(m_rad)
        + (0.019993 - 0.000101 * t) * math.sin(2.0 * m_rad)
        + 0.000289 * math.sin(3.0 * m_rad)
    )
    true_longitude = l0 + c
    true_anomaly = m + c

    # Radius vector in astronomical units (Meeus 25.5).
    eccentricity = 0.016708634 - 0.000042037 * t - 0.0000001267 * t * t
    radius_au = (
        1.000001018
        * (1.0 - eccentricity * eccentricity)
        / (1.0 + eccentricity * math.cos(math.radians(true_anomaly)))
    )

    # Apparent longitude: nutation + aberration (Meeus 25.10).
    omega = 125.04 - 1934.136 * t
    apparent_longitude = (
        true_longitude - 0.00569 - 0.00478 * math.sin(math.radians(omega))
    )

    # Obliquity of the ecliptic with the nutation correction (Meeus 25.8).
    epsilon0 = (
        23.0
        + 26.0 / 60.0
        + 21.448 / 3600.0
        - (46.8150 * t + 0.00059 * t * t - 0.001813 * t * t * t) / 3600.0
    )
    epsilon = epsilon0 + 0.00256 * math.cos(math.radians(omega))

    lam = math.radians(apparent_longitude)
    eps = math.radians(epsilon)
    # Ecliptic latitude of the Sun is ~0; keep the general conversion.
    x = radius_au * math.cos(lam)
    y = radius_au * math.sin(lam) * math.cos(eps)
    z = radius_au * math.sin(lam) * math.sin(eps)

    ra = math.degrees(math.atan2(y, x)) % 360.0
    dec = math.degrees(math.asin(z / radius_au))

    # Unit vector in the equatorial frame of date, then precess to J2000.
    unit_date = (x / radius_au, y / radius_au, z / radius_au)
    unit_j2000 = precess_equatorial_date_to_j2000(unit_date, t)

    return SolarPosition(
        ecliptic_longitude_deg=apparent_longitude % 360.0,
        ecliptic_latitude_deg=0.0,
        distance_au=radius_au,
        distance_km=radius_au * AU_KM,
        right_ascension_deg=ra,
        declination_deg=dec,
        unit_vector_j2000=unit_j2000,
    )


def sun_ecliptic_vector_au(jd_tt: float) -> tuple[float, float, float]:
    """Solar vector in AU using the ecliptic frame of date (auxiliary)."""

    pos = sun_geocentric(jd_tt)
    lam = math.radians(pos.ecliptic_longitude_deg)
    beta = math.radians(pos.ecliptic_latitude_deg)
    return equatorial_from_ecliptic(
        (
            pos.distance_au * math.cos(beta) * math.cos(lam),
            pos.distance_au * math.cos(beta) * math.sin(lam),
            pos.distance_au * math.sin(beta),
        ),
        obliquity_deg=23.439291 - 0.0130042 * julian_centuries_tt(jd_tt),
    )
