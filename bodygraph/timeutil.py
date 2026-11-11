"""Birth time handling: local clock time to UTC, with the traps made visible.

Most wrong charts come from time zone mistakes, not from astronomy. This
module never guesses silently. Ambiguous and non-existent local times, births
before standard time, and births before 1970 all come back with a warning.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class BirthTimeError(ValueError):
    pass


@dataclass
class ResolvedTime:
    utc: datetime
    local: datetime | None = None
    timezone: str | None = None
    utc_offset_minutes: int | None = None
    source: str = "utc"
    warnings: list[dict] = field(default_factory=list)


_TF = None
_TF_LOCK = threading.Lock()


def timezone_at(latitude: float, longitude: float) -> str:
    global _TF
    with _TF_LOCK:
        if _TF is None:
            from timezonefinder import TimezoneFinder

            _TF = TimezoneFinder(in_memory=True)
        name = _TF.timezone_at(lat=latitude, lng=longitude)
    if not name:
        raise BirthTimeError("No time zone found for these coordinates")
    return name


def _warn(code: str, message: str, **extra) -> dict:
    return {"code": code, "message": message, **extra}


def resolve(
    local: datetime | None = None,
    *,
    utc: datetime | None = None,
    tz: str | None = None,
    utc_offset_minutes: int | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    fold: int | None = None,
) -> ResolvedTime:
    """Turn the caller's birth time into an unambiguous UTC instant.

    Precedence: ``utc``; then ``local`` with ``utc_offset_minutes``; then
    ``local`` with an IANA ``tz``; then ``local`` with coordinates.
    """
    if utc is not None:
        if utc.tzinfo is None:
            utc = utc.replace(tzinfo=timezone.utc)
        return ResolvedTime(utc=utc.astimezone(timezone.utc), source="utc")

    if local is None:
        raise BirthTimeError("Provide either a UTC time or a local time")
    if local.tzinfo is not None:
        u = local.astimezone(timezone.utc)
        off = int(local.utcoffset().total_seconds() // 60)
        return ResolvedTime(utc=u, local=local.replace(tzinfo=None),
                            utc_offset_minutes=off, source="offset_in_timestamp")

    if utc_offset_minutes is not None:
        if not -16 * 60 <= utc_offset_minutes <= 16 * 60:
            raise BirthTimeError("utc_offset_minutes is out of range")
        u = (local - timedelta(minutes=utc_offset_minutes)).replace(tzinfo=timezone.utc)
        return ResolvedTime(utc=u, local=local, utc_offset_minutes=utc_offset_minutes,
                            source="explicit_offset")

    source = "iana_timezone"
    if tz is None:
        if latitude is None or longitude is None:
            raise BirthTimeError(
                "A local time needs a timezone, a utc_offset_minutes, or coordinates")
        tz = timezone_at(latitude, longitude)
        source = "coordinates"
    try:
        zone = ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise BirthTimeError(f"Unknown time zone: {tz}") from exc

    warnings: list[dict] = []
    a = local.replace(tzinfo=zone, fold=0)
    b = local.replace(tzinfo=zone, fold=1)
    off_a, off_b = a.utcoffset(), b.utcoffset()
    # A wall time exists when converting to UTC and back returns it unchanged.
    exists = any(
        x.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) == local
        for x in (a, b))
    chosen = a
    if not exists:
        warnings.append(_warn(
            "nonexistent_local_time",
            "Clocks jumped forward over this time in this zone, so it never "
            "appeared on a clock. The time was read with the offset in force "
            "before the jump. Check the birth record.",
        ))
    elif off_a != off_b:
        chosen = b if fold == 1 else a
        cands = [x.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") for x in (a, b)]
        if fold is None:
            warnings.append(_warn(
                "ambiguous_local_time",
                "Clocks were set back over this time, so it happened twice. "
                "The earlier instant was used. Pass fold=1 for the later one.",
                candidates_utc=cands,
            ))
    u = chosen.astimezone(timezone.utc)
    off = chosen.utcoffset()
    off_min = int(off.total_seconds() // 60)
    if chosen.tzname() == "LMT":
        warnings.append(_warn(
            "local_mean_time",
            "This date is before standard time in this zone. Local mean time "
            "for the zone's reference city was used. If the birth record gives "
            "true local time for another town, pass utc_offset_minutes.",
        ))
    elif local.year < 1970:
        warnings.append(_warn(
            "pre_1970_timezone",
            "Time zone records before 1970 are incomplete for some regions. "
            f"The offset used was UTC{_fmt_offset(off_min)}. Confirm it against the "
            "birth record if the chart matters.",
        ))
    if off.total_seconds() % 60:
        off_min = round(off.total_seconds() / 60)
    return ResolvedTime(utc=u, local=local, timezone=tz, utc_offset_minutes=off_min,
                        source=source, warnings=warnings)


def _fmt_offset(minutes: int) -> str:
    sign = "+" if minutes >= 0 else "-"
    h, m = divmod(abs(minutes), 60)
    return f"{sign}{h:02d}:{m:02d}"


def iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + "Z"
