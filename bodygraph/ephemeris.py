"""Planetary positions.

Two engines sit behind one interface.

``SwissEngine``  Swiss Ephemeris reading its compressed JPL files (SE1). This
                 is the reference engine. It refuses to run if the data files
                 are missing, because the library would otherwise fall back to
                 the lower-precision Moshier theory without telling anyone.

``JplEngine``    An independent reduction straight from NASA JPL Development
                 Ephemeris data (DE421 bundled for tests, any SPK kernel such
                 as DE440 in production) using IAU 2006/2000A precession and
                 nutation from ERFA. It exists to check the Swiss engine and to
                 give a path with no AGPL code.

Every public method takes Terrestrial Time (TT) as a Julian day.
All longitudes are apparent, geocentric, tropical, true equinox of date.
"""
from __future__ import annotations

import math
import os
import threading
from dataclasses import dataclass
from pathlib import Path

BODIES = (
    "sun", "earth", "north_node", "south_node", "moon", "mercury", "venus",
    "mars", "jupiter", "saturn", "uranus", "neptune", "pluto",
)

DEFAULT_EPHE_PATH = str(Path(__file__).resolve().parent.parent / "ephe")


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


def _complete(raw: dict[str, Position]) -> dict[str, Position]:
    """Add Earth and South Node, which sit exactly opposite Sun and North Node."""
    raw["earth"] = Position(_norm(raw["sun"].longitude + 180.0), raw["sun"].speed)
    raw["south_node"] = Position(
        _norm(raw["north_node"].longitude + 180.0), raw["north_node"].speed
    )
    return {b: raw[b] for b in BODIES}


# --------------------------------------------------------------------------
# Swiss Ephemeris
# --------------------------------------------------------------------------
_SWE_TLS = threading.local()


class SwissEngine:
    """The Swiss Ephemeris C library keeps its state, including the data path,
    per thread. A web server answers on many threads, so the path is set on
    each thread before use. Without this, worker threads fall back to the
    Moshier theory and the file check below rejects the request."""

    name = "swisseph"

    def __init__(self, ephe_path: str | None = None, allow_moshier: bool = False):
        import swisseph as swe

        self._swe = swe
        self._lock = threading.Lock()  # the C library keeps global state
        self.ephe_path = ephe_path or os.environ.get("SE_EPHE_PATH") or DEFAULT_EPHE_PATH
        self.allow_moshier = allow_moshier
        self._ids = {
            "sun": swe.SUN, "moon": swe.MOON, "mercury": swe.MERCURY,
            "venus": swe.VENUS, "mars": swe.MARS, "jupiter": swe.JUPITER,
            "saturn": swe.SATURN, "uranus": swe.URANUS, "neptune": swe.NEPTUNE,
            "pluto": swe.PLUTO,
        }
        self.version = swe.version
        # Fail at start-up, not on the first request.
        self.sun(2451545.0)

    @property
    def source(self) -> str:
        return f"Swiss Ephemeris {self.version}, SE1 files (JPL DE431)"

    def _bind(self) -> None:
        if getattr(_SWE_TLS, "path", None) != self.ephe_path:
            self._swe.set_ephe_path(self.ephe_path)
            _SWE_TLS.path = self.ephe_path

    def _calc(self, jd_tt: float, body: int) -> Position:
        swe = self._swe
        want = swe.FLG_SWIEPH | swe.FLG_SPEED
        with self._lock:
            self._bind()
            try:
                xx, ret = swe.calc(jd_tt, body, want)
            except swe.Error as exc:  # date outside the installed files
                raise EphemerisError(str(exc)) from exc
        if not (ret & swe.FLG_SWIEPH) and not self.allow_moshier:
            raise EphemerisError(
                "Swiss Ephemeris data files were not used for this date. "
                f"Check {self.ephe_path} for sepl_*.se1 and semo_*.se1."
            )
        return Position(_norm(xx[0]), xx[3])

    def sun(self, jd_tt: float) -> Position:
        return self._calc(jd_tt, self._swe.SUN)

    def positions(self, jd_tt: float, node: str = "true") -> dict[str, Position]:
        swe = self._swe
        out = {name: self._calc(jd_tt, i) for name, i in self._ids.items()}
        out["north_node"] = self._calc(
            jd_tt, swe.TRUE_NODE if node == "true" else swe.MEAN_NODE
        )
        return _complete(out)

    # time scales ---------------------------------------------------------
    def utc_to_tt(self, y, mo, d, h, mi, s) -> float:
        """UTC calendar date to TT Julian day, leap seconds included."""
        with self._lock:
            self._bind()
            jd_tt, _jd_ut1 = self._swe.utc_to_jd(y, mo, d, h, mi, s, self._swe.GREG_CAL)
        return jd_tt

    def tt_to_utc(self, jd_tt: float) -> tuple[int, int, int, int, int, float]:
        with self._lock:
            self._bind()
            return self._swe.jdet_to_utc(jd_tt, self._swe.GREG_CAL)

    def delta_t_seconds(self, jd_tt: float) -> float:
        with self._lock:
            self._bind()
            return self._swe.deltat(jd_tt) * 86400.0


# --------------------------------------------------------------------------
# Independent JPL reduction
# --------------------------------------------------------------------------
_C_AU_DAY = 173.1446326846693  # speed of light, au/day
_GMSUN_OVER_C2_AU = 9.8706286e-9  # heliocentric gravitational constant / c^2, au


class JplEngine:
    """Apparent places computed directly from JPL DE data.

    Steps: barycentric states from the DE polynomials, light-time iteration,
    gravitational light deflection by the Sun, relativistic annual aberration,
    then frame bias, precession and nutation (IAU 2006/2000A) to the true
    equator and equinox of date, and a rotation by the true obliquity to the
    ecliptic of date.
    """

    name = "jpl"

    def __init__(self, kernel: str | None = None):
        import numpy as np
        import erfa

        self._np, self._erfa = np, erfa
        kernel = kernel or os.environ.get("JPL_KERNEL")
        if kernel:
            from jplephem.spk import SPK

            self._spk = SPK.open(kernel)
            self._legacy = None
            self.source = f"JPL {Path(kernel).name}, IAU 2006/2000A (ERFA)"
            self.AU = 149597870.700
            for pair in ((0, 3), (3, 301), (3, 399), (0, 10)):
                self._spk[pair]  # raises KeyError early if the kernel lacks a segment
        else:
            import de421
            from jplephem import Ephemeris

            self._legacy = Ephemeris(de421)
            self._spk = None
            self.source = "JPL DE421, IAU 2006/2000A (ERFA)"
            self.AU = self._legacy.AU
        self._delta = 1.0 / 1440.0  # one minute, for numerical speeds

    # barycentric position and velocity in au and au/day -------------------
    _SPK_TARGET = {
        "sun": 10, "mercury": 1, "venus": 2, "mars": 4, "jupiter": 5,
        "saturn": 6, "uranus": 7, "neptune": 8, "pluto": 9,
    }

    def _bary(self, name: str, jd_tdb: float):
        np = self._np
        if self._legacy is not None:
            e = self._legacy
            if name == "earth" or name == "moon":
                emb, vemb = e.position_and_velocity("earthmoon", jd_tdb)
                gm, vgm = e.position_and_velocity("moon", jd_tdb)  # geocentric
                k = 1.0 / (1.0 + e.EMRAT)
                p, v = emb - gm * k, vemb - vgm * k
                if name == "moon":
                    p, v = p + gm, v + vgm
            else:
                p, v = e.position_and_velocity(name, jd_tdb)
            return np.ravel(p) / self.AU, np.ravel(v) / self.AU
        s = self._spk
        if name in ("earth", "moon"):
            emb, vemb = s[0, 3].compute_and_differentiate(jd_tdb)
            code = 399 if name == "earth" else 301
            p, v = s[3, code].compute_and_differentiate(jd_tdb)
            p, v = emb + p, vemb + v
        else:
            p, v = s[0, self._SPK_TARGET[name]].compute_and_differentiate(jd_tdb)
        return np.ravel(p) / self.AU, np.ravel(v) / self.AU

    def _tdb(self, jd_tt: float) -> float:
        g = math.radians(357.53 + 0.9856003 * (jd_tt - 2451545.0))
        return jd_tt + (0.001658 * math.sin(g) + 0.000014 * math.sin(2 * g)) / 86400.0

    def _to_ecliptic_of_date(self, jd_tt: float):
        """Rotation matrix: ICRS to true ecliptic and equinox of date."""
        erfa = self._erfa
        rnpb = erfa.pnm06a(jd_tt, 0.0)
        dpsi, deps = erfa.nut06a(jd_tt, 0.0)
        eps = erfa.obl06(jd_tt, 0.0) + deps
        c, s = math.cos(eps), math.sin(eps)
        rx = self._np.array([[1, 0, 0], [0, c, s], [0, -s, c]])
        return rx @ rnpb

    def _apparent_vector(self, name: str, jd_tt: float):
        np, erfa = self._np, self._erfa
        t = self._tdb(jd_tt)
        e_p, e_v = self._bary("earth", t)
        s_p, _ = self._bary("sun", t)
        lt = 0.0
        for _ in range(4):
            b_p, _ = self._bary(name, t - lt)
            geo = b_p - e_p
            dist = float(np.linalg.norm(geo))
            lt = dist / _C_AU_DAY
        unit = geo / dist
        e_helio = e_p - s_p
        em = float(np.linalg.norm(e_helio))
        if name not in ("sun", "moon"):
            # light deflection by the Sun
            sun_then, _ = self._bary("sun", t - lt)
            q = b_p - sun_then
            q_unit = q / float(np.linalg.norm(q))
            unit = erfa.ld(1.0, unit, q_unit, e_helio / em, em, 1e-9)
        v = e_v / _C_AU_DAY
        bm1 = math.sqrt(1.0 - float(v @ v))
        unit = erfa.ab(unit, v, em, bm1)
        return self._to_ecliptic_of_date(jd_tt) @ unit

    def _lon(self, name: str, jd_tt: float) -> float:
        x, y, _ = self._apparent_vector(name, jd_tt)
        return _norm(math.degrees(math.atan2(y, x)))

    def _true_node(self, jd_tt: float) -> float:
        """Ascending node of the Moon's osculating orbit, ecliptic of date."""
        np = self._np
        t = self._tdb(jd_tt)
        e_p, e_v = self._bary("earth", t)
        m_p, m_v = self._bary("moon", t)
        rot = self._to_ecliptic_of_date(jd_tt)
        r, v = rot @ (m_p - e_p), rot @ (m_v - e_v)
        h = np.cross(r, v)
        return _norm(math.degrees(math.atan2(h[0], -h[1])))

    def _mean_node(self, jd_tt: float) -> float:
        t = (jd_tt - 2451545.0) / 36525.0
        return _norm(125.0445479 - 1934.1362891 * t + 0.0020754 * t * t
                     + t ** 3 / 467441.0 - t ** 4 / 60616000.0)

    def _pos(self, fn, jd_tt: float) -> Position:
        d = self._delta
        a, b = fn(jd_tt - d), fn(jd_tt + d)
        diff = (b - a + 540.0) % 360.0 - 180.0
        return Position(fn(jd_tt), diff / (2 * d))

    def sun(self, jd_tt: float) -> Position:
        return self._pos(lambda t: self._lon("sun", t), jd_tt)

    def positions(self, jd_tt: float, node: str = "true") -> dict[str, Position]:
        out = {}
        for name in ("sun", "moon", "mercury", "venus", "mars", "jupiter",
                     "saturn", "uranus", "neptune", "pluto"):
            out[name] = self._pos(lambda t, n=name: self._lon(n, t), jd_tt)
        node_fn = self._true_node if node == "true" else self._mean_node
        out["north_node"] = self._pos(node_fn, jd_tt)
        return _complete(out)


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
    """Engine chosen by HD_ENGINE (swisseph by default, or jpl)."""
    global _ENGINE
    with _ENGINE_LOCK:
        if _ENGINE is None:
            which = os.environ.get("HD_ENGINE", "swisseph").lower()
            _ENGINE = JplEngine() if which == "jpl" else SwissEngine()
        return _ENGINE
