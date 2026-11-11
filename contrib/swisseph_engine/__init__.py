"""Optional Swiss Ephemeris engine. A separate work, licensed AGPL-3.0-or-later.

This adapter is not part of the Bodygraph API and nothing in it is imported
by default. It exists so the NASA JPL engine can be checked against the
library most astrology software uses. See README.md in this folder before
you deploy with it.

Enable:  pip install pyswisseph
         HD_ENGINE=contrib.swisseph_engine:SwissEngine
"""
from __future__ import annotations

import math
import os
import threading
from collections import namedtuple
from pathlib import Path

import swisseph as swe

_Base = namedtuple("Position", "longitude speed")


class Position(_Base):
    @property
    def retrograde(self) -> bool:
        return self.speed < 0


ORDER = ("sun", "earth", "north_node", "south_node", "moon", "mercury", "venus",
         "mars", "jupiter", "saturn", "uranus", "neptune", "pluto")
_IDS = {"sun": swe.SUN, "moon": swe.MOON, "mercury": swe.MERCURY, "venus": swe.VENUS,
        "mars": swe.MARS, "jupiter": swe.JUPITER, "saturn": swe.SATURN,
        "uranus": swe.URANUS, "neptune": swe.NEPTUNE, "pluto": swe.PLUTO}
_TLS = threading.local()


class SwissEphemerisError(RuntimeError):
    pass


class SwissEngine:
    """The C library keeps its state, including the data path, per thread. A
    web server answers on many threads, so the path is set on each thread
    before use. Without this, worker threads fall back to the lower-precision
    Moshier theory and nothing fails. The file check below then rejects it."""

    name = "swisseph"

    def __init__(self, ephe_path: str | None = None):
        self.ephe_path = (ephe_path or os.environ.get("SE_EPHE_PATH")
                          or str(Path(__file__).parent / "ephe"))
        self._lock = threading.Lock()
        self.source = f"Swiss Ephemeris {swe.version}, SE1 files (JPL DE431)"
        self.sun(2451545.0)   # fail at start-up, not on the first request

    def _calc(self, jd_tt: float, body: int) -> Position:
        with self._lock:
            if getattr(_TLS, "path", None) != self.ephe_path:
                swe.set_ephe_path(self.ephe_path)
                _TLS.path = self.ephe_path
            try:
                xx, ret = swe.calc(jd_tt, body, swe.FLG_SWIEPH | swe.FLG_SPEED)
            except swe.Error as exc:
                raise SwissEphemerisError(str(exc)) from exc
        if not ret & swe.FLG_SWIEPH:
            raise SwissEphemerisError(
                f"Swiss Ephemeris data files were not used. Check {self.ephe_path} "
                "for sepl_*.se1 and semo_*.se1.")
        return Position(math.fmod(xx[0], 360.0) % 360.0, xx[3])

    def sun(self, jd_tt: float) -> Position:
        return self._calc(jd_tt, swe.SUN)

    def positions(self, jd_tt: float, node: str = "true") -> dict:
        out = {name: self._calc(jd_tt, i) for name, i in _IDS.items()}
        out["north_node"] = self._calc(jd_tt, swe.TRUE_NODE if node == "true" else swe.MEAN_NODE)
        out["earth"] = Position((out["sun"].longitude + 180.0) % 360.0, out["sun"].speed)
        out["south_node"] = Position((out["north_node"].longitude + 180.0) % 360.0,
                                     out["north_node"].speed)
        return {b: out[b] for b in ORDER}
