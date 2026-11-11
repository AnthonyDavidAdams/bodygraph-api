"""Planetary positions from NASA JPL Development Ephemerides.

The engine reads a JPL ephemeris file and reduces it to what an observer at
the Earth's center sees: apparent, geocentric, tropical longitude on the true
equinox of date.

Steps for each body:
  1. Barycentric position and velocity from the JPL polynomials.
  2. Light time: where the body was when the light now arriving left it.
  3. Gravitational deflection of that light by the Sun.
  4. Annual aberration from the Earth's own motion.
  5. Frame bias, precession and nutation (IAU 2006/2000A, via ERFA) to the
     true equator of date, then a turn by the true obliquity to the ecliptic.

Choose the data file with HD_EPHEMERIS:
  de440            NASA's current file, 1550 to 2650 (default, package naif-de440)
  de421            the 2008 file, 1900 to 2200 (package de421)
  /path/to/x.bsp   any JPL SPK planetary kernel, such as de440s.bsp or de441

A different engine can be plugged in with HD_ENGINE=package.module:ClassName.
It needs ``name``, ``source``, ``sun(jd_tt)`` and ``positions(jd_tt, node)``.

Every public method takes Terrestrial Time (TT) as a Julian day.
"""
from __future__ import annotations

import importlib
import math
import os
import threading
from dataclasses import dataclass
from pathlib import Path

import erfa
import numpy as np

BODIES = (
    "sun", "earth", "north_node", "south_node", "moon", "mercury", "venus",
    "mars", "jupiter", "saturn", "uranus", "neptune", "pluto",
)
_PLANETS = ("sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn",
            "uranus", "neptune", "pluto")


class EphemerisError(RuntimeError):
    pass


@dataclass(frozen=True)
class Position:
    longitude: float  # degrees, 0 <= x < 360
    speed: float      # degrees per day

    @property
    def retrograde(self) -> bool:
        return self.speed < 0


def _norm(x: float) -> float:
    x = math.fmod(x, 360.0)
    return x + 360.0 if x < 0 else x


def complete(raw: dict[str, Position]) -> dict[str, Position]:
    """Add Earth and South Node, which sit exactly opposite Sun and North Node."""
    raw["earth"] = Position(_norm(raw["sun"].longitude + 180.0), raw["sun"].speed)
    raw["south_node"] = Position(
        _norm(raw["north_node"].longitude + 180.0), raw["north_node"].speed)
    return {b: raw[b] for b in BODIES}


_C_AU_DAY = 173.1446326846693      # speed of light, au per day
_AU_KM = 149597870.700
_SRS = 1.97412574336e-8            # Schwarzschild radius of the Sun, au
_PRECESSION_DEG_DAY = 50.288 / 3600.0 / 365.25   # general precession in longitude
_SPK_TARGET = {"sun": 10, "mercury": 1, "venus": 2, "mars": 4, "jupiter": 5,
               "saturn": 6, "uranus": 7, "neptune": 8, "pluto": 9}


def _rot(m, v):
    return (m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
            m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
            m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2])


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


class _Chebyshev:
    """Scalar evaluation of one SPK type 2 segment: position and velocity.

    jplephem maps the file. Its own evaluator is built for arrays of dates
    and costs about 75 microseconds a call. A chart needs about ninety calls,
    so this plain-float Clenshaw recurrence is used instead.
    """

    def __init__(self, segment, au_km: float):
        if segment.data_type != 2:
            raise EphemerisError("Only SPK type 2 (Chebyshev position) segments are supported")
        self.init, self.intlen, self.coef = segment._data   # coef[k][axis][record], high order first
        self.n = self.coef.shape[2]
        self.au = au_km
        self.start_jd, self.end_jd = segment.start_jd, segment.end_jd
        self._cache: dict[int, list] = {}

    def pv(self, jd_tdb: float):
        sec = (jd_tdb - 2451545.0) * 86400.0 - self.init
        idx = int(sec // self.intlen)
        if idx == self.n:
            idx -= 1
        if not 0 <= idx < self.n:
            raise EphemerisError("date outside the ephemeris file")
        rec = self._cache.get(idx)
        if rec is None:
            if len(self._cache) > 256:
                self._cache.clear()
            rec = self._cache[idx] = self.coef[:, :, idx].tolist()
        s = 2.0 * (sec - idx * self.intlen) / self.intlen - 1.0
        s2 = 2.0 * s
        ax = ay = az = bx = by = bz = 0.0          # w0 and w1 of the recurrence
        dax = day = daz = dbx = dby = dbz = 0.0    # the same for the derivative
        for cx, cy, cz in rec[:-1]:
            # derivative first: it uses the w1 of this step, which is the old w0
            dax, dbx = 2.0 * ax + dax * s2 - dbx, dax
            day, dby = 2.0 * ay + day * s2 - dby, day
            daz, dbz = 2.0 * az + daz * s2 - dbz, daz
            ax, bx = cx + s2 * ax - bx, ax
            ay, by = cy + s2 * ay - by, ay
            az, bz = cz + s2 * az - bz, az
        cx, cy, cz = rec[-1]
        k = 1.0 / self.au
        pos = ((cx + s * ax - bx) * k, (cy + s * ay - by) * k, (cz + s * az - bz) * k)
        r = 2.0 * 86400.0 / self.intlen * k
        vel = ((ax + s * dax - dbx) * r, (ay + s * day - dby) * r, (az + s * daz - dbz) * r)
        return pos, vel


class JplEngine:
    name = "jpl"

    def __init__(self, dataset: str | None = None):
        dataset = dataset or os.environ.get("HD_EPHEMERIS") or "de440"
        self._legacy = None
        self._seg = {}
        key = dataset.lower()
        if key == "de421":
            try:
                import de421
                from jplephem import Ephemeris
            except ImportError as exc:
                raise EphemerisError("HD_EPHEMERIS=de421 needs: pip install de421") from exc
            self._legacy = Ephemeris(de421)
            for n in ("earthmoon", "moon", "sun", *list(_SPK_TARGET)[1:]):
                self._legacy.position(n, 2451545.0)          # load now, not per thread
            self._au = float(self._legacy.AU)
            self._emrat = float(self._legacy.EMRAT)
            self.jd_min, self.jd_max = float(self._legacy.jalpha), float(self._legacy.jomega)
            label = "DE421"
        else:
            if key == "de440":
                try:
                    import naif_de440
                except ImportError as exc:
                    raise EphemerisError(
                        "HD_EPHEMERIS=de440 needs: pip install naif-de440") from exc
                path = naif_de440.de440
                label = "DE440"
            else:
                path = dataset
                if not Path(path).is_file():
                    raise EphemerisError(f"Ephemeris file not found: {path}")
                label = Path(path).stem.upper()
            from jplephem.spk import SPK

            self._kernel = SPK.open(path)
            need = [(0, 3), (3, 399), (3, 301), *[(0, c) for c in _SPK_TARGET.values()]]
            lo, hi = -1e99, 1e99
            for pair in need:
                try:
                    seg = _Chebyshev(self._kernel[pair], _AU_KM)
                except KeyError as exc:
                    raise EphemerisError(
                        f"{path} has no segment {pair}. A planetary kernel is required.") from exc
                self._seg[pair] = seg
                lo, hi = max(lo, seg.start_jd), min(hi, seg.end_jd)
            self.jd_min, self.jd_max = lo, hi
        self.dataset = label
        self.source = f"NASA JPL {label}, IAU 2006/2000A"

    # -- raw states, au and au/day, barycentric ICRF -----------------------
    def _pv(self, name: str, jd_tdb: float):
        if self._legacy is not None:
            e = self._legacy
            try:
                if name in ("earth", "moon"):
                    emb, vemb = e.position_and_velocity("earthmoon", jd_tdb)
                    gm, vgm = e.position_and_velocity("moon", jd_tdb)   # geocentric
                    k = 1.0 / (1.0 + self._emrat)
                    p, v = emb - gm * k, vemb - vgm * k
                    if name == "moon":
                        p, v = p + gm, v + vgm
                else:
                    p, v = e.position_and_velocity(name, jd_tdb)
            except (ValueError, IndexError) as exc:
                raise EphemerisError(self.range_message()) from exc
            return (tuple((np.ravel(p) / self._au).tolist()),
                    tuple((np.ravel(v) / self._au).tolist()))
        if name in ("earth", "moon"):
            (ex, ey, ez), (evx, evy, evz) = self._seg[(0, 3)].pv(jd_tdb)
            (px, py, pz), (vx, vy, vz) = self._seg[(3, 399 if name == "earth" else 301)].pv(jd_tdb)
            return (ex + px, ey + py, ez + pz), (evx + vx, evy + vy, evz + vz)
        return self._seg[(0, _SPK_TARGET[name])].pv(jd_tdb)

    def year_range(self) -> tuple[int, int]:
        """First and last full calendar years the data file covers."""
        return (int(2000 + (self.jd_min - 2451545.0) / 365.25) + 1,
                int(2000 + (self.jd_max - 2451545.0) / 365.25) - 1)

    def range_message(self) -> str:
        y0, y1 = self.year_range()
        return f"{self.dataset} covers the years {y0} to {y1}"

    @staticmethod
    def _tdb(jd_tt: float) -> float:
        g = math.radians(357.53 + 0.9856003 * (jd_tt - 2451545.0))
        return jd_tt + (0.001658 * math.sin(g) + 0.000014 * math.sin(2 * g)) / 86400.0

    @staticmethod
    def _to_ecliptic_of_date(jd_tt: float):
        """Rotation matrix: ICRS to the true ecliptic and equinox of date."""
        _dpsi, deps, epsa, _rb, _rp, _rbp, _rn, rbpn = erfa.pn06a(jd_tt, 0.0)
        eps = float(epsa) + float(deps)
        c, s = math.cos(eps), math.sin(eps)
        return (np.array([[1.0, 0.0, 0.0], [0.0, c, s], [0.0, -s, c]]) @ rbpn).tolist()

    def _frame(self, jd_tt: float):
        if not (self.jd_min + 1 < jd_tt < self.jd_max - 1):
            raise EphemerisError(self.range_message())
        t = self._tdb(jd_tt)
        e_p, e_v = self._pv("earth", t)
        s_p, _ = self._pv("sun", t)
        return t, e_p, e_v, s_p, self._to_ecliptic_of_date(jd_tt)

    def _apparent(self, name: str, frame) -> Position:
        t, e_p, e_v, s_p, rot = frame
        # Light time. Two passes leave an error far below a milliarcsecond.
        b_p, b_v = self._pv(name, t)
        geo = _sub(b_p, e_p)
        dist = math.sqrt(_dot(geo, geo))
        b_p, b_v = self._pv(name, t - dist / _C_AU_DAY)
        geo = _sub(b_p, e_p)
        dist = math.sqrt(_dot(geo, geo))
        p = (geo[0] / dist, geo[1] / dist, geo[2] / dist)

        e_h = _sub(e_p, s_p)                      # Sun to observer
        em = math.sqrt(_dot(e_h, e_h))
        e_u = (e_h[0] / em, e_h[1] / em, e_h[2] / em)
        if name not in ("sun", "moon"):
            # Light deflection by the Sun (the ERFA "ld" formula).
            q = _sub(b_p, s_p)
            qn = math.sqrt(_dot(q, q))
            q = (q[0] / qn, q[1] / qn, q[2] / qn)
            qpe = (q[0] + e_u[0], q[1] + e_u[1], q[2] + e_u[2])
            w = _SRS / em / max(_dot(q, qpe), 1e-9)
            d = _cross(p, _cross(e_u, q))
            p = (p[0] + w * d[0], p[1] + w * d[1], p[2] + w * d[2])
        # Annual aberration (the ERFA "ab" formula, relativistic).
        v = (e_v[0] / _C_AU_DAY, e_v[1] / _C_AU_DAY, e_v[2] / _C_AU_DAY)
        bm1 = math.sqrt(1.0 - _dot(v, v))
        pdv = _dot(p, v)
        w1 = 1.0 + pdv / (1.0 + bm1)
        w2 = _SRS / em
        a = tuple(p[i] * bm1 + w1 * v[i] + w2 * (v[i] - pdv * p[i]) for i in range(3))
        x, y, _ = _rot(rot, a)
        # Rate of change from the relative velocity, plus precession of the equinox.
        gx, gy, _ = _rot(rot, geo)
        vx, vy, _ = _rot(rot, _sub(b_v, e_v))
        speed = math.degrees((gx * vy - gy * vx) / (gx * gx + gy * gy)) + _PRECESSION_DEG_DAY
        return Position(_norm(math.degrees(math.atan2(y, x))), speed)

    def _true_node(self, jd_tt: float, rot) -> float:
        """Ascending node of the Moon's osculating orbit, ecliptic of date."""
        t = self._tdb(jd_tt)
        e_p, e_v = self._pv("earth", t)
        m_p, m_v = self._pv("moon", t)
        h = _cross(_rot(rot, _sub(m_p, e_p)), _rot(rot, _sub(m_v, e_v)))
        return _norm(math.degrees(math.atan2(h[0], -h[1])))

    @staticmethod
    def _mean_node(jd_tt: float) -> float:
        t = (jd_tt - 2451545.0) / 36525.0
        return _norm(125.0445479 - 1934.1362891 * t + 0.0020754 * t * t
                     + t ** 3 / 467441.0 - t ** 4 / 60616000.0)

    # -- public ------------------------------------------------------------
    def sun(self, jd_tt: float) -> Position:
        return self._apparent("sun", self._frame(jd_tt))

    def positions(self, jd_tt: float, node: str = "true") -> dict[str, Position]:
        frame = self._frame(jd_tt)
        out = {name: self._apparent(name, frame) for name in _PLANETS}
        d = 1.0 / 1440.0
        if node == "true":
            rot = frame[4]
            a, b = self._true_node(jd_tt - d, rot), self._true_node(jd_tt + d, rot)
            out["north_node"] = Position(self._true_node(jd_tt, rot),
                                         ((b - a + 540.0) % 360.0 - 180.0) / (2 * d))
        else:
            a, b = self._mean_node(jd_tt - d), self._mean_node(jd_tt + d)
            out["north_node"] = Position(self._mean_node(jd_tt),
                                         ((b - a + 540.0) % 360.0 - 180.0) / (2 * d))
        return complete(out)


# --------------------------------------------------------------------------
# The Design moment
# --------------------------------------------------------------------------
def solve_solar_arc(engine, jd_tt_birth: float, arc: float = 88.0,
                    tolerance_deg: float = 2e-9) -> float:
    """Return the TT Julian day when the Sun stood ``arc`` degrees earlier.

    Newton's method on the Sun's apparent longitude. The Sun's longitude is
    strictly increasing and nearly linear, so this converges in three or four
    steps. A bisection fallback guards the bracket. A double-precision Julian
    day resolves about 40 microseconds, which bounds the tolerance.
    """
    target = _norm(engine.sun(jd_tt_birth).longitude - arc)

    def err(jd: float) -> tuple[float, float]:
        p = engine.sun(jd)
        return (p.longitude - target + 540.0) % 360.0 - 180.0, p.speed

    jd = jd_tt_birth - arc / 0.985647  # mean solar motion, degrees per day
    lo, hi = jd_tt_birth - arc / 0.94, jd_tt_birth - arc / 1.03
    for _ in range(12):
        e, speed = err(jd)
        if abs(e) < tolerance_deg:
            return jd
        if e > 0:
            hi = min(hi, jd)
        else:
            lo = max(lo, jd)
        step = jd - e / speed
        jd = step if lo < step < hi else (lo + hi) / 2.0
    for _ in range(80):
        e, _ = err(jd)
        if abs(e) < tolerance_deg or hi - lo < 2e-9:
            return jd
        if e > 0:
            hi = jd
        else:
            lo = jd
        jd = (lo + hi) / 2.0
    raise EphemerisError("Design moment solver did not converge")


_ENGINE = None
_ENGINE_LOCK = threading.Lock()


def get_engine():
    """The process-wide engine, built once from HD_ENGINE and HD_EPHEMERIS."""
    global _ENGINE
    with _ENGINE_LOCK:
        if _ENGINE is None:
            spec = os.environ.get("HD_ENGINE", "jpl")
            if spec == "jpl":
                _ENGINE = JplEngine()
            else:
                try:
                    module, _, cls = spec.partition(":")
                    _ENGINE = getattr(importlib.import_module(module), cls)()
                except (ImportError, AttributeError, ValueError) as exc:
                    raise EphemerisError(
                        f"HD_ENGINE={spec!r} must be 'jpl' or 'package.module:ClassName'") from exc
        return _ENGINE
