"""Time-scale handling.

The application uses UTC for every user-facing timestamp and converts to
Terrestrial Time (TT) for the ephemeris algorithms. TT-UTC is a constant
69.184 s for the epoch of this prototype (TAI-UTC = 37 s since 2017-01-01).

No timezone localisation is performed: all mission times are displayed and
computed in UTC. This is deliberate — mission planning avoids ambiguity and the
lunar surface has no civil time zones.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .constants import DAYS_PER_CENTURY, JD_J2000, TT_MINUS_UTC_SECONDS


def parse_datetime_utc(value: str | datetime) -> datetime:
    """Parse an ISO-8601 timestamp and normalise it to timezone-aware UTC.

    Naive timestamps are interpreted as UTC (documented in the API schema).
    """

    if isinstance(value, datetime):
        dt = value
    else:
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError as exc:  # pragma: no cover - pydantic reports first
            raise ValueError(f"Invalid ISO-8601 datetime: {value!r}") from exc

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def julian_date_utc(dt: datetime) -> float:
    """Julian Date from a UTC datetime (Meeus, ch. 7)."""

    dt = parse_datetime_utc(dt)
    year = dt.year
    month = dt.month
    day = (
        dt.day
        + (dt.hour + (dt.minute + (dt.second + dt.microsecond / 1e6) / 60.0) / 60.0)
        / 24.0
    )

    if month <= 2:
        year -= 1
        month += 12

    a = year // 100
    b = 2 - a + a // 4
    return (
        int(365.25 * (year + 4716))
        + int(30.6001 * (month + 1))
        + day
        + b
        - 1524.5
    )


def julian_date_tt(dt: datetime) -> float:
    """Julian Date in Terrestrial Time for a UTC datetime."""

    return julian_date_utc(dt) + TT_MINUS_UTC_SECONDS / 86400.0


def julian_centuries_tt(jd_tt: float) -> float:
    """Julian centuries since J2000.0 in TT."""

    return (jd_tt - JD_J2000) / DAYS_PER_CENTURY


def julian_days_tt(jd_tt: float) -> float:
    """Julian days since J2000.0 in TT."""

    return jd_tt - JD_J2000


def jd_to_datetime_utc(jd_utc: float) -> datetime:
    """Convert a Julian Date (UTC scale) to an aware UTC datetime."""

    # Meeus, ch. 7 (valid for the Gregorian calendar used by this project).
    z = int(jd_utc + 0.5)
    f = jd_utc + 0.5 - z
    alpha = int((z - 1867216.25) / 36524.25)
    a = z + 1 + alpha - alpha // 4
    b = a + 1524
    c = int((b - 122.1) / 365.25)
    d = int(365.25 * c)
    e = int((b - d) / 30.6001)

    day_fraction = b - d - int(30.6001 * e) + f
    day = int(day_fraction)
    month = e - 1 if e < 14 else e - 13
    year = c - 4716 if month > 2 else c - 4715

    seconds = (day_fraction - day) * 86400.0
    # Round to microseconds to avoid floating point noise.
    whole_seconds = int(round(seconds))
    base = datetime(year, month, day, tzinfo=timezone.utc)
    return base + timedelta(seconds=whole_seconds)


def isoformat_z(dt: datetime) -> str:
    """Compact ISO-8601 UTC string with a trailing Z."""

    return parse_datetime_utc(dt).isoformat(timespec="seconds").replace("+00:00", "Z")


def format_utc(dt: datetime) -> str:
    """Human-readable UTC label used in reports."""

    return parse_datetime_utc(dt).strftime("%Y-%m-%d %H:%M:%S UTC")
