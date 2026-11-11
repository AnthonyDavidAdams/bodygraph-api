"""UTC to Terrestrial Time (TT) and back.

Planetary positions are tabulated against a uniform time scale, TT. Clocks
run on UTC, which follows the Earth's uneven rotation.

From 1972 on, TT - UTC is exact: 32.184 s plus the leap seconds, taken from
the IAU SOFA/ERFA table.

Before 1972 a civil time is treated as Universal Time, and TT - UT (Delta T)
comes from the cubic splines of Morrison, Stephenson, Hohenkerk and Zawilski,
"Addendum 2020 to Measurement of the Earth's rotation: 720 BC to AD 2015"
(Proc. R. Soc. A 477, 2021), Table S15. They fit the observational record to
well under a second after 1800. One second moves the Moon half an arcsecond.

Future dates assume no further leap seconds.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import warnings

import erfa

# ERFA flags years past its leap second table. The constant offset is intended.
warnings.filterwarnings("ignore", category=erfa.ErfaWarning)

_LEAP_ERA = datetime(1972, 1, 1, tzinfo=timezone.utc)
_J2000 = datetime(2000, 1, 1, 12, tzinfo=timezone.utc)
_JD_1972 = 2441317.5


# Table S15: (year from, year to, a3, a2, a1, a0). With t = (y - from) / (to - from),
# Delta T = ((a3 t + a2) t + a1) t + a0 seconds.
_S15 = (
    (1500, 1600, 16.197, -6.572, -192.841, 292.343),
    (1600, 1650, 3.018, 10.505, -78.697, 109.127),
    (1650, 1720, -2.127, 38.333, -68.089, 43.952),
    (1720, 1800, -37.939, 41.731, 2.507, 12.068),
    (1800, 1810, 1.918, -1.126, -3.481, 18.367),
    (1810, 1820, -3.812, 4.629, 0.021, 15.678),
    (1820, 1830, 3.25, -6.806, -2.157, 16.516),
    (1830, 1840, -0.096, 2.944, -6.018, 10.804),
    (1840, 1850, -0.539, 2.658, -0.416, 7.634),
    (1850, 1855, -0.883, 0.261, 1.642, 9.338),
    (1855, 1860, 1.558, -2.389, -0.486, 10.357),
    (1860, 1865, -2.477, 2.284, -0.591, 9.04),
    (1865, 1870, 2.72, -5.148, -3.456, 8.255),
    (1870, 1875, -0.914, 3.011, -5.593, 2.371),
    (1875, 1880, -0.039, 0.269, -2.314, -1.126),
    (1880, 1885, 0.563, 0.152, -1.893, -3.21),
    (1885, 1890, -1.438, 1.842, 0.101, -4.388),
    (1890, 1895, 1.871, -2.474, -0.531, -3.884),
    (1895, 1900, -0.232, 3.138, 0.134, -5.017),
    (1900, 1905, -1.257, 2.443, 5.715, -1.977),
    (1905, 1910, 0.72, -1.329, 6.828, 4.923),
    (1910, 1915, -0.825, 0.831, 6.33, 11.142),
    (1915, 1920, 0.262, -1.643, 5.518, 17.479),
    (1920, 1925, 0.008, -0.856, 3.02, 21.617),
    (1925, 1930, 0.127, -0.831, 1.333, 23.789),
    (1930, 1935, 0.142, -0.449, 0.052, 24.418),
    (1935, 1940, 0.702, -0.022, -0.419, 24.164),
    (1940, 1945, -1.106, 2.086, 1.645, 24.426),
    (1945, 1950, 0.614, -1.232, 2.499, 27.05),
    (1950, 1953, -0.277, 0.22, 1.127, 28.932),
    (1953, 1956, 0.631, -0.61, 0.737, 30.002),
    (1956, 1959, -0.799, 1.282, 1.409, 30.76),
    (1959, 1962, 0.507, -1.115, 1.577, 32.652),
    (1962, 1965, 0.199, 0.406, 0.868, 33.621),
    (1965, 1968, -0.414, 1.002, 2.275, 35.093),
    (1968, 1971, 0.202, -0.242, 3.035, 37.956),
    (1971, 1974, -0.229, 0.364, 3.157, 40.951),
)


def delta_t_seconds(year: float) -> float:
    """TT - UT in seconds for a decimal year, valid 1500 to 1974."""
    if year < _S15[0][0] or year >= _S15[-1][1]:
        u = (year - 1825.0) / 100.0            # long-term parabola, same authors
        return -320.0 + 32.5 * u * u
    lo, hi = 0, len(_S15) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if year >= _S15[mid][1]:
            lo = mid + 1
        else:
            hi = mid
    x0, x1, a3, a2, a1, a0 = _S15[lo]
    t = (year - x0) / (x1 - x0)
    return ((a3 * t + a2) * t + a1) * t + a0


def _decimal_year(jd: float) -> float:
    return 2000.0 + (jd - 2451544.5) / 365.2425


def _jd_utc(utc: datetime) -> float:
    return 2451545.0 + (utc - _J2000) / timedelta(days=1)


def utc_to_tt(utc: datetime) -> float:
    """Julian day in TT for a timezone-aware datetime."""
    utc = utc.astimezone(timezone.utc)
    if utc >= _LEAP_ERA:
        sec = utc.second + utc.microsecond / 1e6
        u1, u2 = erfa.dtf2d("UTC", utc.year, utc.month, utc.day, utc.hour, utc.minute, sec)
        a1, a2 = erfa.utctai(u1, u2)
        t1, t2 = erfa.taitt(a1, a2)
        return float(t1 + t2)
    jd = _jd_utc(utc)
    return jd + delta_t_seconds(_decimal_year(jd)) / 86400.0


def tt_to_utc(jd_tt: float) -> datetime:
    """Timezone-aware UTC datetime for a TT Julian day."""
    if jd_tt >= _JD_1972 + 42.184 / 86400.0:
        a1, a2 = erfa.tttai(jd_tt, 0.0)
        u1, u2 = erfa.taiutc(a1, a2)
        y, mo, d, hmsf = erfa.d2dtf("UTC", 6, u1, u2)
        h, mi, s, micro = (int(v) for v in hmsf)
        base = datetime(int(y), int(mo), int(d), h, mi, min(s, 59), micro, tzinfo=timezone.utc)
        return base + timedelta(seconds=s - min(s, 59))   # a leap second reads as :59 + 1 s
    jd = jd_tt - delta_t_seconds(_decimal_year(jd_tt)) / 86400.0
    jd = jd_tt - delta_t_seconds(_decimal_year(jd)) / 86400.0
    return _J2000 + timedelta(days=jd - 2451545.0)


def tt_minus_utc_seconds(utc: datetime) -> float:
    return (utc_to_tt(utc) - _jd_utc(utc.astimezone(timezone.utc))) * 86400.0
