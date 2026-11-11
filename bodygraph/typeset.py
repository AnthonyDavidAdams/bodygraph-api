"""Text as vector outlines.

Charts are embedded in pages, emails, PDFs and design tools that do not share
fonts. Shaping the text here (HarfBuzz, with kerning) and emitting outlines
means every viewer shows the same letterforms, with no font download. Each
glyph outline is defined once per drawing and referenced with <use>, which
keeps the file small.
"""
from __future__ import annotations

import contextvars
import threading
from functools import lru_cache
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

_DIR = Path(__file__).parent / "fonts"
FONTS = {
    "regular": "Barlow-Regular.ttf",
    "medium": "Barlow-Medium.ttf",
    "semibold": "Barlow-SemiBold.ttf",
    "num": "BarlowSemiCondensed-Medium.ttf",
    "numbold": "BarlowSemiCondensed-SemiBold.ttf",
}


# fontTools loads glyphs lazily and HarfBuzz fonts are not safe to share
# across threads, so every font operation runs under one lock. Results are
# cached, so the lock is held only for text never seen before.
_LOCK = threading.RLock()


@lru_cache(maxsize=None)
def _font(key: str):
    path = _DIR / FONTS[key]
    tt = TTFont(str(path))
    face = hb.Face(path.read_bytes())
    return tt, tt.getGlyphSet(), hb.Font(face), tt["head"].unitsPerEm, tt.getGlyphOrder()


@lru_cache(maxsize=8192)
def _shape(text: str, key: str, tabular: bool):
    """Shape a run. Returns ((glyph id, x, y) ..., advance, units per em)."""
    with _LOCK:
        tt, glyphs, hbfont, upem, order = _font(key)
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(hbfont, buf, {"kern": True, "liga": True, "tnum": tabular, "lnum": True})
        x, out = 0.0, []
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            out.append((info.codepoint, x + pos.x_offset, pos.y_offset))
            x += pos.x_advance
        return tuple(out), x, upem


@lru_cache(maxsize=4096)
def _outline(key: str, gid: int) -> str:
    with _LOCK:
        tt, glyphs, _, _, order = _font(key)
        pen = SVGPathPen(glyphs, ntos=lambda v: f"{v:.0f}")
        glyphs[order[gid]].draw(pen)
        return pen.getCommands()


_SESSION: contextvars.ContextVar = contextvars.ContextVar("typeset_session", default=None)


class Session:
    """Collects the glyphs one drawing uses, so each outline is stored once."""

    def __init__(self):
        self.used: dict[tuple[str, int], str] = {}

    def ref(self, key: str, gid: int) -> str:
        return self.used.setdefault((key, gid), f"t{len(self.used):x}")

    def defs(self) -> str:
        body = "".join(f'<path id="{ref}" d="{_outline(k, g)}"/>'
                       for (k, g), ref in self.used.items() if _outline(k, g))
        return f"<defs>{body}</defs>"

    def __enter__(self):
        self._token = _SESSION.set(self)
        return self

    def __exit__(self, *exc):
        _SESSION.reset(self._token)


def measure(text: str, size: float, font: str = "regular", tabular: bool = False) -> float:
    _, adv, upem = _shape(text, font, tabular)
    return adv * size / upem


def text(x: float, y: float, s: str, size: float, *, font: str = "regular",
         fill: str = "#000", anchor: str = "start", tabular: bool = False,
         opacity: float | None = None) -> str:
    """SVG for ``s`` with its baseline at (x, y). Call inside a Session."""
    if not s:
        return ""
    session = _SESSION.get()
    if session is None:
        raise RuntimeError("typeset.text() needs an active typeset.Session")
    glyphs, adv, upem = _shape(s, font, tabular)
    k = size / upem
    w = adv * k
    if anchor == "middle":
        x -= w / 2
    elif anchor == "end":
        x -= w
    op = f' opacity="{opacity}"' if opacity is not None else ""
    uses = "".join(
        f'<use href="#{session.ref(font, gid)}"'
        + (f' x="{gx:.0f}"' if gx else "") + (f' y="{gy:.0f}"' if gy else "") + "/>"
        for gid, gx, gy in glyphs if _outline(font, gid))
    return (f'<g fill="{fill}"{op} transform="translate({x:.2f} {y:.2f}) '
            f'scale({k:.5f} {-k:.5f})">{uses}</g>')


def wrap(s: str, size: float, width: float, font: str = "regular") -> list[str]:
    lines, cur = [], ""
    for word in s.split():
        trial = f"{cur} {word}".strip()
        if cur and measure(trial, size, font) > width:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines
