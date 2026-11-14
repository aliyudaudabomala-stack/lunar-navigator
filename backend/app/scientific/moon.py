"""Lunar and Earth geometry.

The Moon's geocentric position is computed with the truncated ELP-2000/82
series published in Meeus (ch. 47). Terms involving the Moon's mean anomaly are
scaled by the eccentricity correction factor E. The retained terms give an
accuracy of a few arcseconds in longitude/latitude and ~1 km in distance for
1900-2100 — adequate for horizon geometry at 240 m terrain resolution.

Earth as seen from the Moon is simply the anti-direction of the Moon's
geocentric position vector (topocentric parallax is applied later). This makes
Earth's apparent motion in the lunar sky — libration — emerge directly from the
ephemeris rather than being approximated.

Reference frames: positions are computed in the ecliptic/equatorial frame of
date and precessed to J2000/ICRF, matching the IAU lunar orientation model.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

from .constants import AU_KM, EARTH_EQUATORIAL_RADIUS_KM, MOON_RADIUS_KM
from .frames import (
    body_vector_from_selenographic,
    equatorial_from_ecliptic,
    mat_transpose_vec,
    mat_vec,
    moon_orientation_matrix,
    norm,
    precession_matrix_date_to_j2000,
    selenographic_from_body_vector,
    unit,
    Vec3,
)
from .sun import sun_geocentric
from .time import julian_centuries_tt, julian_days_tt

#: Solar radius (km), IAU 2015 nominal value.
SUN_RADIUS_KM = 695_700.0

# Meeus ch. 47 periodic terms: (D, M, M', F, coefficient in 1e-6 deg or 1e-3 km)
_LONGITUDE_TERMS = (
    (0, 0, 1, 0, 6288774),
    (2, 0, -1, 0, 1274027),
    (2, 0, 0, 0, 658314),
    (0, 0, 2, 0, 213618),
    (0, 1, 0, 0, -185116),
    (0, 0, 0, 2, -114332),
    (2, 0, -2, 0, 58793),
    (2, -1, -1, 0, 57066),
    (2, 0, 1, 0, 53322),
    (2, -1, 0, 0, 45758),
    (0, 1, -1, 0, -40923),
    (1, 0, 0, 0, -34720),
    (0, 1, 1, 0, -30383),
    (2, 0, 0, -2, 15327),
    (0, 0, 1, 2, -12528),
    (0, 0, 1, -2, 10980),
    (4, 0, -1, 0, 10675),
    (0, 0, 3, 0, 10034),
    (4, 0, -2, 0, 8548),
    (2, 1, -1, 0, -7888),
    (2, 1, 0, 0, -6766),
    (1, 0, -1, 0, -5163),
    (1, 1, 0, 0, 4987),
    (2, -1, 1, 0, 4036),
    (2, 0, 2, 0, 3994),
    (4, 0, 0, 0, 3861),
    (2, 0, -3, 0, 3665),
    (0, 1, -2, 0, -2689),
    (2, 0, -1, 2, -2602),
    (2, -1, -2, 0, 2390),
    (1, 0, 1, 0, -2348),
    (2, -2, 0, 0, 2236),
    (0, 1, 2, 0, -2120),
    (0, 2, 0, 0, -2069),
    (2, -2, -1, 0, 2048),
    (2, 0, 1, -2, -1773),
    (2, 0, 0, 2, -1595),
    (4, -1, -1, 0, 1215),
    (0, 0, 2, 2, -1110),
    (3, 0, -1, 0, -892),
    (2, 1, 1, 0, -810),
    (4, -1, -2, 0, 759),
    (0, 2, -1, 0, -713),
    (2, 2, -1, 0, -700),
    (2, 1, -2, 0, 691),
    (2, -1, 0, -2, 596),
    (4, 0, 1, 0, 549),
    (0, 0, 4, 0, 537),
    (4, -1, 0, 0, 520),
    (1, 0, -2, 0, -487),
    (2, 1, -1, 2, -399),
    (0, 0, 2, -2, -381),
    (1, 1, 1, 0, 351),
    (3, 0, -2, 0, -340),
    (4, 0, -3, 0, 330),
    (2, -1, 2, 0, 327),
    (0, 2, 1, 0, -323),
    (1, 1, -1, 0, 299),
    (2, 0, 3, 0, 294),
)

_LATITUDE_TERMS = (
    (0, 0, 0, 1, 5128122),
    (0, 0, 1, 1, 280602),
    (0, 0, 1, -1, 277693),
    (2, 0, 0, -1, 173237),
    (2, 0, -1, 1, 55413),
    (2, 0, -1, -1, 46271),
    (2, 0, 0, 1, 32573),
    (0, 0, 2, 1, 17198),
    (2, 0, 1, -1, 9266),
    (0, 0, 2, -1, 8822),
    (2, -1, 0, -1, 8216),
    (2, 0, -2, -1, 4324),
    (2, 0, 1, 1, 4200),
    (2, 1, 0, -1, -3359),
    (2, -1, -1, 1, 2463),
    (2, -1, 0, 1, 2211),
    (2, -1, 1, -1, 2065),
    (0, 1, -1, -1, -1870),
    (2, 0, 2, 1, 1828),
    (0, 1, 0, 1, -1794),
    (0, 0, 3, 1, -1749),
    (0, 1, -1, 1, -1565),
    (1, 0, 0, 1, -1491),
    (0, 1, 1, 1, -1475),
    (0, 1, 1, -1, -1410),
    (0, 1, 0, -1, -1344),
    (1, 0, 0, -1, -1335),
    (0, 0, 3, -1, 1107),
    (4, 0, 0, -1, 1021),
    (4, 0, -1, 1, 833),
    (0, 0, 1, -3, 777),
    (4, 0, -2, -1, 671),
    (2, 0, -1, -3, 607),
    (2, 0, 1, -3, 596),
    (2, -1, -1, -1, 491),
    (2, 0, -3, 1, 451),
    (0, 0, 2, 3, -451),
    (2, 0, 2, -1, 439),
    (2, 0, 3, 1, 422),
    (2, 0, 3, -1, 421),
    (2, -1, -2, 1, 366),
    (2, 0, -1, 3, 351),
    (2, -1, 2, 1, 331),
    (4, -1, 0, -1, 315),
    (2, 0, -1, 1, 302),
    (0, 2, 0, 1, -283),
    (0, 0, 4, 1, 223),
    (2, 0, -2, 3, 223),
    (0, 1, 2, -1, -220),
    (2, 0, 1, 3, 220),
    (2, 0, 0, 3, 181),
    (4, 0, -1, -1, 181),
    (0, 0, 1, 5, 176),
)

_DISTANCE_TERMS = (
    (0, 0, 1, 0, -20905355),
    (2, 0, -1, 0, -3699111),
    (2, 0, 0, 0, -2955968),
    (0, 0, 2, 0, -569925),
    (0, 1, 0, 0, 48888),
    (0, 0, 0, 2, -3149),
    (2, 0, -2, 0, 246158),
    (2, -1, -1, 0, -152138),
    (2, 0, 1, 0, -170733),
    (2, -1, 0, 0, -204586),
    (0, 1, -1, 0, -129620),
    (1, 0, 0, 0, 108743),
    (0, 1, 1, 0, 104755),
    (2, 0, 0, -2, 10321),
    (4, 0, -1, 0, 79661),
    (0, 0, 3, 0, -34782),
    (2, 0, 1, -2, -23210),
    (2, 0, -2, 2, -21636),
    (2, 1, 0, 0, 24208),
    (2, 1, -1, 0, 30824),
    (4, 0, -2, 0, -8379),
    (2, -1, 1, 0, -16675),
    (2, 0, 2, 0, -12831),
    (2, 0, -3, 0, -10445),
    (4, 0, 0, 0, -11650),
)


def _mean_elements(jd_tt: float) -> tuple[float, float, float, float, float, float]:
    """Return L', D, M, M', F in degrees and the eccentricity factor E."""

    t = julian_centuries_tt(jd_tt)
    lp = (
        218.3164477
        + 481267.88123421 * t
        - 0.0015786 * t**2
        + t**3 / 538_841.0
        - t**4 / 65_194_000.0
    )
    d = (
        297.8501921
        + 445267.1114034 * t
        - 0.0018819 * t**2
        + t**3 / 545_868.0
        - t**4 / 113_065_000.0
    )
    m = 357.5291092 + 35999.0502909 * t - 0.0001536 * t**2 + t**3 / 24_490_000.0
    mp = (
        134.9633964
        + 477198.8675055 * t
        + 0.0087414 * t**2
        + t**3 / 69_699.0
        - t**4 / 14_712_000.0
    )
    f = (
        93.2720950
        + 483202.0175233 * t
        - 0.0036539 * t**2
        - t**3 / 3_526_000.0
        + t**4 / 863_310_000.0
    )
    e = 1.0 - 0.002516 * t - 0.0000074 * t**2
    return lp % 360.0, d % 360.0, m % 360.0, mp % 360.0, f % 360.0, e


def _series(terms, d: float, m: float, mp: float, f: float, e: float) -> float:
    total = 0.0
    for cd, cm, cmp_, cf, coeff in terms:
        arg = math.radians(cd * d + cm * m + cmp_ * mp + cf * f)
        factor = 1.0
        if abs(cm) == 1:
            factor = e
        elif abs(cm) == 2:
            factor = e * e
        total += coeff * factor * math.sin(arg)
    return total


def _distance_series(d: float, m: float, mp: float, f: float, e: float) -> float:
    total = 0.0
    for cd, cm, cmp_, cf, coeff in _DISTANCE_TERMS:
        arg = math.radians(cd * d + cm * m + cmp_ * mp + cf * f)
        factor = 1.0
        if abs(cm) == 1:
            factor = e
        elif abs(cm) == 2:
            factor = e * e
        total += coeff * factor * math.cos(arg)
    return total


@dataclass(frozen=True)
class LunarEphemeris:
    """Everything the app needs for one instant of lunar geometry."""

    jd_tt: float
    moon_ecliptic_longitude_deg: float
    moon_ecliptic_latitude_deg: float
    moon_distance_km: float
    moon_position_j2000_km: Vec3
    earth_direction_j2000: Vec3
    sun_direction_j2000: Vec3
    sun_distance_from_moon_km: float
    sub_earth_longitude_deg: float
    sub_earth_latitude_deg: float
    sub_solar_longitude_deg: float
    sub_solar_latitude_deg: float
    phase_angle_deg: float
    illuminated_fraction: float
    sun_angular_radius_deg: float
    earth_angular_radius_deg: float
    orientation_matrix: tuple[Vec3, Vec3, Vec3]


def moon_geocentric_ecliptic(jd_tt: float) -> tuple[float, float, float]:
    """Geometric geocentric ecliptic longitude, latitude and distance.

    Returns ``(lambda_deg, beta_deg, distance_km)`` referred to the mean
    equinox of date. Additive terms follow Meeus 47.1-47.3.
    """

    lp, d, m, mp, f, e = _mean_elements(jd_tt)
    t = julian_centuries_tt(jd_tt)

    sum_l = _series(_LONGITUDE_TERMS, d, m, mp, f, e)
    sum_b = _series(_LATITUDE_TERMS, d, m, mp, f, e)
    sum_r = _distance_series(d, m, mp, f, e)

    a1 = 119.75 + 131.849 * t
    a2 = 53.09 + 479264.290 * t
    # A3 is only used for the (omitted) physical libration terms.

    longitude = (
        lp
        + sum_l / 1_000_000.0
        + 0.003958 * math.sin(math.radians(a1))
        + 0.001962 * math.sin(math.radians(lp - f))
        + 0.000318 * math.sin(math.radians(a2))
    ) % 360.0
    latitude = sum_b / 1_000_000.0
    distance = 385_000.56 + sum_r / 1000.0
    return longitude, latitude, distance


def lunar_ephemeris(jd_tt: float) -> LunarEphemeris:
    """Compute Sun/Earth geometry in the lunar body-fixed frame."""

    t = julian_centuries_tt(jd_tt)
    lon_m, lat_m, dist_m = moon_geocentric_ecliptic(jd_tt)

    # Obliquity of the ecliptic of date (mean).
    epsilon = 23.439291 - 0.0130042 * t - 1.64e-7 * t * t + 5.04e-7 * t**3
    moon_ecl = (
        dist_m * math.cos(math.radians(lat_m)) * math.cos(math.radians(lon_m)),
        dist_m * math.cos(math.radians(lat_m)) * math.sin(math.radians(lon_m)),
        dist_m * math.sin(math.radians(lat_m)),
    )
    moon_date = equatorial_from_ecliptic(moon_ecl, epsilon)
    precession = precession_matrix_date_to_j2000(t)
    moon_j2000 = mat_vec(precession, moon_date)
    moon_unit_j2000 = unit(moon_j2000)

    sun = sun_geocentric(jd_tt)
    sun_j2000 = (sun.distance_km * sun.unit_vector_j2000[0],
                 sun.distance_km * sun.unit_vector_j2000[1],
                 sun.distance_km * sun.unit_vector_j2000[2])

    # Selenocentric vectors (km). The Sun's distance is measured from the Moon.
    sun_from_moon = (
        sun_j2000[0] - moon_j2000[0],
        sun_j2000[1] - moon_j2000[1],
        sun_j2000[2] - moon_j2000[2],
    )
    sun_distance_moon = norm(sun_from_moon)

    orientation = moon_orientation_matrix(jd_tt)
    # body = R * inertial; rows are body axes in ICRF.
    sun_body = mat_vec(orientation, sun_from_moon)
    earth_body = mat_vec(orientation, (-moon_j2000[0], -moon_j2000[1], -moon_j2000[2]))

    earth_unit_body = unit(earth_body)
    sun_unit_body = unit(sun_body)
    sub_earth_lon, sub_earth_lat = selenographic_from_body_vector(earth_unit_body)
    sub_solar_lon, sub_solar_lat = selenographic_from_body_vector(sun_unit_body)

    # Phase angle at the Moon between Earth and Sun.
    cos_phase = (
        earth_unit_body[0] * sun_unit_body[0]
        + earth_unit_body[1] * sun_unit_body[1]
        + earth_unit_body[2] * sun_unit_body[2]
    )
    phase = math.degrees(math.acos(max(-1.0, min(1.0, cos_phase))))

    return LunarEphemeris(
        jd_tt=jd_tt,
        moon_ecliptic_longitude_deg=lon_m,
        moon_ecliptic_latitude_deg=lat_m,
        moon_distance_km=dist_m,
        moon_position_j2000_km=moon_j2000,
        earth_direction_j2000=(-moon_unit_j2000[0], -moon_unit_j2000[1], -moon_unit_j2000[2]),
        sun_direction_j2000=unit(sun_from_moon),
        sun_distance_from_moon_km=sun_distance_moon,
        sub_earth_longitude_deg=sub_earth_lon,
        sub_earth_latitude_deg=sub_earth_lat,
        sub_solar_longitude_deg=sub_solar_lon,
        sub_solar_latitude_deg=sub_solar_lat,
        phase_angle_deg=phase,
        illuminated_fraction=(1.0 + math.cos(math.radians(phase))) / 2.0,
        sun_angular_radius_deg=math.degrees(math.asin(SUN_RADIUS_KM / sun_distance_moon)),
        earth_angular_radius_deg=math.degrees(
            math.asin(EARTH_EQUATORIAL_RADIUS_KM / dist_m)
        ),
        orientation_matrix=orientation,
    )


def target_vectors_body(eph: LunarEphemeris) -> tuple[Vec3, Vec3]:
    """Earth and Sun selenocentric vectors in km (for topocentric geometry)."""

    earth = (-eph.moon_position_j2000_km[0], -eph.moon_position_j2000_km[1], -eph.moon_position_j2000_km[2])
    # Reconstruct the Sun vector from its unit direction and distance.
    d = eph.sun_direction_j2000
    sun = (d[0] * eph.sun_distance_from_moon_km,
           d[1] * eph.sun_distance_from_moon_km,
           d[2] * eph.sun_distance_from_moon_km)
    # Rotate into the body-fixed frame.
    orientation = eph.orientation_matrix
    return mat_vec(orientation, earth), mat_vec(orientation, sun)


def subsolar_point(jd_tt: float) -> tuple[float, float]:
    """Sub-solar selenographic longitude/latitude (deg)."""

    eph = lunar_ephemeris(jd_tt)
    return eph.sub_solar_longitude_deg, eph.sub_solar_latitude_deg


def body_point_from_latlon(lat_deg: float, lon_deg: float, radius_km: float = MOON_RADIUS_KM) -> Vec3:
    """Convenience wrapper used by visualisation payloads."""

    return body_vector_from_selenographic(lat_deg, lon_deg, radius_km)
