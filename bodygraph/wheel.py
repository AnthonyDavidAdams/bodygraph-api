"""The Rave Mandala: ecliptic longitude to gate, line, color, tone, base.

The wheel starts with Gate 41 at 2 deg 00' Aquarius (302 deg tropical) and runs
through 64 gates of 5 deg 37' 30". Each gate holds 6 lines, each line 6 colors,
each color 6 tones, each tone 5 bases. That gives 69,120 base cells of exactly
18.75 arcseconds. All subdivision is done with integers on that grid, so
there is no floating point drift between levels.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

WHEEL_START = 302.0
GATE_ORDER = (
    41, 19, 13, 49, 30, 55, 37, 63, 22, 36, 25, 17, 21, 51, 42, 3,
    27, 24, 2, 23, 8, 20, 16, 35, 45, 12, 15, 52, 39, 53, 62, 56,
    31, 33, 7, 4, 29, 59, 40, 64, 47, 6, 46, 18, 48, 57, 32, 50,
    28, 44, 1, 43, 14, 34, 9, 5, 26, 11, 10, 58, 38, 54, 61, 60,
)
GATE_INDEX = {g: i for i, g in enumerate(GATE_ORDER)}

CELLS = 69120                    # 64 * 6 * 6 * 6 * 5
CELL_DEG = 360.0 / CELLS         # 18.75 arcseconds
GATE_DEG, LINE_DEG, COLOR_DEG, TONE_DEG, BASE_DEG = 5.625, 0.9375, 0.15625, 0.15625 / 6, CELL_DEG
LEVEL_CELLS = {"gate": 1080, "line": 180, "color": 30, "tone": 5, "base": 1}

SIGNS = ("Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra",
         "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces")


@dataclass(frozen=True)
class Activation:
    gate: int
    line: int
    color: int
    tone: int
    base: int
    longitude: float
    wheel_offset: float     # degrees from the start of Gate 41

    @property
    def gate_line(self) -> str:
        return f"{self.gate}.{self.line}"


def wheel_offset(longitude: float) -> float:
    x = math.fmod(longitude - WHEEL_START, 360.0)
    if x < 0:
        x += 360.0
    return 0.0 if x >= 360.0 else x


def activation(longitude: float) -> Activation:
    x = wheel_offset(longitude)
    # A longitude within 1e-9 degrees below a boundary counts as on it. That is
    # four millionths of an arcsecond, far finer than any ephemeris, and it
    # absorbs the rounding of the subtraction above.
    cell = int((x + 1e-9) / CELL_DEG) % CELLS
    return Activation(
        gate=GATE_ORDER[cell // 1080],
        line=cell // 180 % 6 + 1,
        color=cell // 30 % 6 + 1,
        tone=cell // 5 % 6 + 1,
        base=cell % 5 + 1,
        longitude=longitude,
        wheel_offset=x,
    )


def boundary_distance(longitude: float, level: str) -> tuple[float, float]:
    """Degrees back to the previous boundary and forward to the next one."""
    size = LEVEL_CELLS[level] * CELL_DEG
    x = wheel_offset(longitude)
    back = math.fmod(x, size)
    return back, size - back


def gate_span(gate: int) -> tuple[float, float]:
    """Tropical longitudes where a gate begins and ends."""
    start = (WHEEL_START + GATE_INDEX[gate] * GATE_DEG) % 360.0
    return start, (start + GATE_DEG) % 360.0


def opposite_gate(gate: int) -> int:
    return GATE_ORDER[(GATE_INDEX[gate] + 32) % 64]


def zodiac(longitude: float) -> dict:
    lon = longitude % 360.0
    sign = int(lon // 30)
    within = lon - sign * 30
    total = round(within * 3600)
    if total >= 108000:
        total = 107999
    d, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return {"sign": SIGNS[sign], "degree": d, "minute": m, "second": s,
            "formatted": f"{d}°{m:02d}'{s:02d}\" {SIGNS[sign]}"}
