"""Coordinate-frame utilities.

Conventions
-----------
* Inertial frame: ICRF/J2000 equatorial, +x toward the J2000 equinox, +z toward
  the north celestial pole.
* Lunar body-fixed frame: mean Earth/polar axis (ME) frame, +x through the mean
  prime meridian, +z through the north pole. Selenographic longitude is
  positive east, latitude positive north.
* Local frame: east-north-up (ENU) at the observer. Azimuth is measured
  clockwise from true north (0 = N, 90 = E); elevation is positive above the
  local geocentric horizon.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

from .constants import DEG, MOON_POLE_DEC_DEG, MOON_POLE_RA_DEG, MOON_PRIME_MERIDIAN_DEG

Vec3 = tuple[float, float, float]


def dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def norm(a: Vec3) -> float:
    return math.sqrt(dot(a, a))


def unit(a: Vec3) -> Vec3:
    n = norm(a)
    if n == 0:
        raise ValueError("Cannot normalise a zero vector")
    return (a[0] / n, a[1] / n, a[2] / n)


def add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def mul(a: Vec3, s: float) -> Vec3:
    return (a[0] * s, a[1] * s, a[2] * s)


def sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def mat_vec(m: tuple[Vec3, Vec3, Vec3], v: Vec3) -> Vec3:
    """Multiply a 3x3 matrix (rows) by a column vector."""

    return (dot(m[0], v), dot(m[1], v), dot(m[2], v))


def mat_transpose_vec(m: tuple[Vec3, Vec3, Vec3], v: Vec3) -> Vec3:
    """Apply the transpose of a rotation matrix (inverse rotation)."""

    return (
        m[0][0] * v[0] + m[1][0] * v[1] + m[2][0] * v[2],
        m[0][1] * v[0] + m[1][1] * v[1] + m[2][1] * v[2],
        m[0][2] * v[0] + m[1][2] * v[1] + m[2][2] * v[2],
    )


def equatorial_from_ecliptic(v: Vec3, obliquity_deg: float) -> Vec3:
    """Rotate an ecliptic vector into the equatorial frame of the same epoch."""

    eps = obliquity_deg * DEG
    x, y, z = v
    return (x, y * math.cos(eps) - z * math.sin(eps), y * math.sin(eps) + z * math.cos(eps))


def precession_matrix_date_to_j2000(t_centuries: float) -> tuple[Vec3, Vec3, Vec3]:
    """IAU 1976 precession matrix from the mean equator/equinox of date to J2000.

    Meeus eq. 21.2 with the signs arranged so that applying this matrix to a
    vector expressed in the frame of date yields its J2000 representation.
    """

    t = t_centuries
    zeta = (2306.2181 * t + 0.30188 * t * t + 0.017998 * t**3) / 3600.0
    z = (2306.2181 * t + 1.09468 * t * t + 0.018203 * t**3) / 3600.0
    theta = (2004.3109 * t - 0.42665 * t * t - 0.041833 * t**3) / 3600.0

    cz, sz = math.cos(math.radians(zeta)), math.sin(math.radians(zeta))
    cZ, sZ = math.cos(math.radians(z)), math.sin(math.radians(z))
    ct, st = math.cos(math.radians(theta)), math.sin(math.radians(theta))

    # Rotation of the frame by +zeta about z, +theta about y, +z about z is the
    # J2000->date transformation; its transpose is date->J2000.
    r3_zeta = ((cz, sz, 0.0), (-sz, cz, 0.0), (0.0, 0.0, 1.0))
    r2_theta = ((ct, 0.0, -st), (0.0, 1.0, 0.0), (st, 0.0, ct))
    r3_z = ((cZ, sZ, 0.0), (-sZ, cZ, 0.0), (0.0, 0.0, 1.0))

    # Compose date->J2000 = Rz(-z) * Ry(-theta) * Rz(-zeta).
    r3_neg_z = ((cZ, -sZ, 0.0), (sZ, cZ, 0.0), (0.0, 0.0, 1.0))
    r2_neg_theta = ((ct, 0.0, st), (0.0, 1.0, 0.0), (-st, 0.0, ct))
    r3_neg_zeta = ((cz, -sz, 0.0), (sz, cz, 0.0), (0.0, 0.0, 1.0))

    # Matrix product r3_neg_z * r2_neg_theta * r3_neg_zeta.
    m1 = _matmul(r3_neg_z, r2_neg_theta)
    return _matmul(m1, r3_neg_zeta)


def _matmul(a: tuple[Vec3, Vec3, Vec3], b: tuple[Vec3, Vec3, Vec3]) -> tuple[Vec3, Vec3, Vec3]:
    return (
        (dot(a[0], (b[0][0], b[1][0], b[2][0])), dot(a[0], (b[0][1], b[1][1], b[2][1])), dot(a[0], (b[0][2], b[1][2], b[2][2]))),
        (dot(a[1], (b[0][0], b[1][0], b[2][0])), dot(a[1], (b[0][1], b[1][1], b[2][1])), dot(a[1], (b[0][2], b[1][2], b[2][2]))),
        (dot(a[2], (b[0][0], b[1][0], b[2][0])), dot(a[2], (b[0][1], b[1][1], b[2][1])), dot(a[2], (b[0][2], b[1][2], b[2][2]))),
    )


def precess_equatorial_date_to_j2000(v: Vec3, t_centuries: float) -> Vec3:
    return mat_vec(precession_matrix_date_to_j2000(t_centuries), v)


#: IAU WGCCRE periodic terms for the lunar pole and prime meridian
#: (pck00010.tpc / Archinal et al. 2011). These encode the Cassini state and
#: the 18.6-year precession of the lunar spin axis; omitting them would remove
#: the Moon's 1.54 deg polar seasons entirely.
_MOON_NUT_RA = (-3.8787, -0.1204, 0.0700, -0.0172, 0.0, 0.0072, 0.0, 0.0, 0.0, -0.0052, 0.0, 0.0, 0.0043)
_MOON_NUT_DEC = (1.5419, 0.0239, -0.0278, 0.0068, 0.0, -0.0029, 0.0009, 0.0, 0.0, 0.0008, 0.0, 0.0, -0.0009)
_MOON_NUT_PM = (3.5610, 0.1208, -0.0642, 0.0158, 0.0252, -0.0066, -0.0047, -0.0046, 0.0028, 0.0052, 0.0040, 0.0019, -0.0044)


def _moon_nutation_arguments(d: float) -> tuple[float, ...]:
    """The 13 standard IAU lunar nutation arguments E1..E13 (degrees)."""

    return (
        125.045 - 0.0529921 * d,
        250.089 - 0.1059842 * d,
        260.008 + 13.0120009 * d,
        176.625 + 13.3407154 * d,
        357.529 + 0.9856003 * d,
        311.589 + 26.4057084 * d,
        134.963 + 13.0649930 * d,
        276.617 + 0.3287146 * d,
        34.226 + 1.7484877 * d,
        15.134 - 0.1589763 * d,
        119.743 + 0.0036096 * d,
        239.961 + 0.1643573 * d,
        25.053 + 12.9590088 * d,
    )


def moon_orientation_matrix(jd_tt: float) -> tuple[Vec3, Vec3, Vec3]:
    """ICRF -> lunar body-fixed rotation matrix from IAU 2015 elements.

    The matrix rows are the body-fixed x, y, z axes expressed in ICRF. The
    periodic terms are required: they carry the 1.54 deg Cassini-state tilt that
    produces the Moon's polar seasons.
    """

    d = jd_tt - 2451545.0
    t = d / 36525.0

    alpha_deg = MOON_POLE_RA_DEG[0] + MOON_POLE_RA_DEG[1] * t
    delta_deg = MOON_POLE_DEC_DEG[0] + MOON_POLE_DEC_DEG[1] * t
    w_deg = (
        MOON_PRIME_MERIDIAN_DEG[0]
        + MOON_PRIME_MERIDIAN_DEG[1] * d
        + MOON_PRIME_MERIDIAN_DEG[2] * d * d
    )

    for idx, e_deg in enumerate(_moon_nutation_arguments(d)):
        e = math.radians(e_deg)
        alpha_deg += _MOON_NUT_RA[idx] * math.sin(e)
        delta_deg += _MOON_NUT_DEC[idx] * math.cos(e)
        w_deg += _MOON_NUT_PM[idx] * math.sin(e)

    alpha0 = math.radians(alpha_deg)
    delta0 = math.radians(delta_deg)
    w = math.radians(w_deg)

    pole = (
        math.cos(delta0) * math.cos(alpha0),
        math.cos(delta0) * math.sin(alpha0),
        math.sin(delta0),
    )
    node = (-math.sin(alpha0), math.cos(alpha0), 0.0)
    east_at_node = cross(pole, node)

    x_axis = add(mul(node, math.cos(w)), mul(east_at_node, math.sin(w)))
    y_axis = cross(pole, x_axis)
    return (unit(x_axis), unit(y_axis), unit(pole))


def selenographic_from_body_vector(v_body: Vec3) -> tuple[float, float]:
    """Convert a body-fixed vector to (longitude east, latitude) in degrees."""

    lon = math.degrees(math.atan2(v_body[1], v_body[0])) % 360.0
    lat = math.degrees(math.asin(max(-1.0, min(1.0, v_body[2] / norm(v_body)))))
    return lon, lat


def body_vector_from_selenographic(lat_deg: float, lon_deg: float, radius_km: float) -> Vec3:
    """Body-fixed Cartesian position for a planetocentric lat/lon and radius."""

    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    return (
        radius_km * math.cos(lat) * math.cos(lon),
        radius_km * math.cos(lat) * math.sin(lon),
        radius_km * math.sin(lat),
    )


@dataclass(frozen=True)
class LocalSkyPosition:
    """Apparent position of a target in the local ENU frame."""

    azimuth_deg: float
    elevation_deg: float
    distance_km: float
    angular_radius_deg: float
    above_geometric_horizon: bool


def local_sky_position(
    target_body_vec_km: Vec3,
    site_body_vec_km: Vec3,
    *,
    target_radius_km: float,
) -> LocalSkyPosition:
    """Topocentric azimuth/elevation of a target seen from a lunar site.

    Both vectors are expressed in the lunar body-fixed frame. Topocentric
    parallax is included by differencing the actual positions; for the Earth it
    is up to ~0.26 deg, which is comparable to the Earth's angular radius, so it
    must not be ignored.
    """

    topo = sub(target_body_vec_km, site_body_vec_km)
    distance = norm(topo)
    d = unit(topo)

    lat = math.asin(site_body_vec_km[2] / norm(site_body_vec_km))
    lon = math.atan2(site_body_vec_km[1], site_body_vec_km[0])

    up = (
        math.cos(lat) * math.cos(lon),
        math.cos(lat) * math.sin(lon),
        math.sin(lat),
    )
    east = (-math.sin(lon), math.cos(lon), 0.0)
    north = (-math.sin(lat) * math.cos(lon), -math.sin(lat) * math.sin(lon), math.cos(lat))

    x = dot(d, east)
    y = dot(d, north)
    z = dot(d, up)

    az = math.degrees(math.atan2(x, y)) % 360.0
    el = math.degrees(math.asin(max(-1.0, min(1.0, z))))
    angular_radius = math.degrees(math.asin(min(1.0, target_radius_km / distance)))

    return LocalSkyPosition(
        azimuth_deg=az,
        elevation_deg=el,
        distance_km=distance,
        angular_radius_deg=angular_radius,
        above_geometric_horizon=el > 0.0,
    )


def site_body_vector_km(lat_deg: float, lon_deg: float, elevation_m: float = 0.0) -> Vec3:
    """Body-fixed position of a surface site on the LOLA reference sphere."""

    from .constants import MOON_RADIUS_M

    radius_km = (MOON_RADIUS_M + elevation_m) / 1000.0
    return body_vector_from_selenographic(lat_deg, lon_deg, radius_km)


def spherical_horizon_dip_deg(elevation_m: float) -> float:
    """Dip of the geometric horizon for an observer at height h (no terrain).

    Uses the small-angle form acos(R/(R+h)) so that the result is positive
    downward. Included for transparency; terrain horizons supersede it when a
    DEM is available.
    """

    from .constants import MOON_RADIUS_M

    ratio = MOON_RADIUS_M / (MOON_RADIUS_M + max(0.0, elevation_m))
    return math.degrees(math.acos(ratio))


def horizontal_to_body_vector(az_deg: float, el_deg: float, lat_deg: float, lon_deg: float) -> Vec3:
    """Unit vector in the body-fixed frame for a local az/el direction.

    Useful for horizon visualisations and for overlaying the local horizon on
    the 3D Moon.
    """

    lat, lon = math.radians(lat_deg), math.radians(lon_deg)
    az, el = math.radians(az_deg), math.radians(el_deg)
    up = (math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat))
    east = (-math.sin(lon), math.cos(lon), 0.0)
    north = (-math.sin(lat) * math.cos(lon), -math.sin(lat) * math.sin(lon), math.cos(lat))
    return unit(
        add(
            add(mul(north, math.cos(el) * math.cos(az)), mul(east, math.cos(el) * math.sin(az))),
            mul(up, math.sin(el)),
        )
    )
