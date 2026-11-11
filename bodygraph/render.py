"""SVG bodygraph renderer.

Design rules:
  * Red is Design, ink is Personality. Nothing else on the page is red.
  * Centers are pale tints. The saturated marks are the data.
  * Every channel is two half bands, one per gate, so a hanging gate reads
    at a glance and a full channel reads as one bar.
  * Text is emitted as outlines, so the chart looks the same everywhere.
"""
from __future__ import annotations

import html
import math

from . import data as D
from . import geometry as geo
from . import typeset as ts
from .ephemeris import BODIES

THEMES = {
    "light": dict(
        paper="#FFFFFF", ink="#12161C", muted="#6B7280", faint="#9AA1AC", rule="#E3E6EB",
        design="#D7301F", personality="#12161C",
        channel_edge="#C5CAD3", channel_fill="#FFFFFF",
        center_open="#FFFFFF", center_stroke="#8E96A3", gate_idle="#8B93A0",
        badge_ring="#FFFFFF", badge_text="#FFFFFF",
        tints=dict(yellow=("#FBE9A6", "#A08419"), green=("#C3E3C7", "#3F7F4C"),
                   brown=("#EAD3BD", "#8A5E3B"), red=("#F8C6BA", "#A9503E")),
        mono=("#DDE2EA", "#5E6876"),
        person_a="#0B8A83", person_b="#7446D8", transit="#2563D9",
    ),
    "dark": dict(
        paper="#0E1218", ink="#EEF1F5", muted="#98A1AE", faint="#6C7583", rule="#252C37",
        design="#FF5A47", personality="#EEF1F5",
        channel_edge="#3A4350", channel_fill="#0E1218",
        center_open="#0E1218", center_stroke="#5C6675", gate_idle="#7B8493",
        badge_ring="#0E1218", badge_text="#0E1218",
        tints=dict(yellow=("#5E4F16", "#D9B93F"), green=("#234A2C", "#7DC48A"),
                   brown=("#4E3724", "#C99B73"), red=("#5A2A21", "#EE9280")),
        mono=("#28303B", "#9AA4B2"),
        person_a="#35C9BF", person_b="#A98BFF", transit="#6AA3FF",
    ),
}
CENTER_TINT = {
    "head": "yellow", "ajna": "green", "throat": "brown", "g": "yellow", "heart": "red",
    "spleen": "brown", "solar_plexus": "brown", "sacral": "red", "root": "brown",
}
ORDER = BODIES  # sun, earth, nodes, moon, then the planets outward


def _f(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".")


def _poly(points, fill, extra="") -> str:
    pts = " ".join(f"{_f(x)},{_f(y)}" for x, y in points)
    return f'<polygon points="{pts}" fill="{fill}"{extra}/>'


# --------------------------------------------------------------------------
# planet glyphs, drawn on a 16 x 16 grid with one stroke weight
# --------------------------------------------------------------------------
_GLYPHS = {
    "sun": '<circle cx="8" cy="8" r="5.6"/><circle cx="8" cy="8" r="1.25" fill="{c}" stroke="none"/>',
    "earth": '<circle cx="8" cy="8" r="5.6"/><path d="M8 2.4V13.6M2.4 8H13.6"/>',
    "moon": '<path d="M10.9 2.5A5.9 5.9 0 1 0 10.9 13.5A6.9 6.9 0 0 1 10.9 2.5Z"/>',
    "north_node": '<path d="M5.2 10.9C2.2 8.2 3.6 2.6 8 2.6S13.8 8.2 10.8 10.9"/>'
                  '<circle cx="4.1" cy="12.2" r="1.7"/><circle cx="11.9" cy="12.2" r="1.7"/>',
    "south_node": '<path d="M5.2 5.1C2.2 7.8 3.6 13.4 8 13.4S13.8 7.8 10.8 5.1"/>'
                  '<circle cx="4.1" cy="3.8" r="1.7"/><circle cx="11.9" cy="3.8" r="1.7"/>',
    "mercury": '<circle cx="8" cy="7.2" r="3"/><path d="M8 10.2V15M5.7 12.7H10.3'
               'M5 1.2A3 3 0 0 0 11 1.2"/>',
    "venus": '<circle cx="8" cy="5.6" r="3.8"/><path d="M8 9.4V15M5.3 12.3H10.7"/>',
    "mars": '<circle cx="6.5" cy="9.5" r="4"/><path d="M9.4 6.6L13.9 2.1M10 2.1H13.9V6"/>',
    "jupiter": '<path d="M3.2 4.6C4 2.4 8.4 2 8.4 5.4C8.4 8 5.4 9.4 3.2 10.8H13M10.7 2.2V14.6"/>',
    "saturn": '<path d="M5.4 1.6V10.6M3.2 4H7.8M5.4 7.6C6.6 5.6 10.8 5.2 10.8 8.4'
              'C10.8 10.6 8.6 11.4 9 13.2C9.2 14.4 10.8 14.6 11.9 13.8"/>',
    "uranus": '<path d="M3.6 1.8V8.6M12.4 1.8V8.6M3.6 5.2H12.4M8 1.8V9.9"/>'
              '<circle cx="8" cy="12.2" r="2.2"/>',
    "neptune": '<path d="M3.2 2.2C3.2 9.4 12.8 9.4 12.8 2.2M8 2.2V15M5.4 12.2H10.6"/>',
    "pluto": '<path d="M4.8 14.4V2H8.6A3.4 3.4 0 0 1 8.6 8.8H4.8M4.8 14.4H12"/>',
}


def _glyph(body: str, x: float, y: float, size: float, color: str) -> str:
    k = size / 16.0
    inner = _GLYPHS[body].replace("{c}", color)
    return (f'<g transform="translate({_f(x - size / 2)} {_f(y - size / 2)}) scale({k:.4f})" '
            f'fill="none" stroke="{color}" stroke-width="1.5" stroke-linecap="round" '
            f'stroke-linejoin="round">{inner}</g>')


def _arrow(x: float, y: float, direction: str, color: str, length: float = 26.0) -> str:
    s = -1 if direction == "left" else 1
    x0, x1 = x - s * length / 2, x + s * length / 2
    return (f'<path d="M{_f(x0)} {_f(y)}H{_f(x1)}M{_f(x1 - s * 7)} {_f(y - 6)}'
            f'L{_f(x1)} {_f(y)}L{_f(x1 - s * 7)} {_f(y + 6)}" fill="none" stroke="{color}" '
            f'stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>')


# --------------------------------------------------------------------------
# the bodygraph itself
# --------------------------------------------------------------------------
def _band(p, q, colors, wide=geo.BAND + 2.0) -> str:
    """One piece of channel. Two colours split the band lengthwise."""
    if len(colors) > 1:
        h = wide / 2.0
        return (_poly(geo.band_polygon(p, q, h + 0.3, -h / 2), colors[0])
                + _poly(geo.band_polygon(p, q, h + 0.3, h / 2), colors[1]))
    return _poly(geo.band_polygon(p, q, wide), colors[0])


def _extend(p, q, by=1.2):
    """Lengthen p->q a little at q so adjoining pieces overlap without a seam."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    n = math.hypot(dx, dy) or 1.0
    return (q[0] + dx / n * by, q[1] + dy / n * by)


def _merge(sets) -> tuple:
    seen = []
    for cols in sets:
        for c in cols:
            if c not in seen:
                seen.append(c)
    return tuple(seen[:2])


def bodygraph_group(t: dict, gate_colors: dict[int, tuple], defined_channels: set,
                    center_states: dict[str, str], center_colors: str = "traditional",
                    gate_notes: dict[int, str] | None = None) -> str:
    """The 600 x 910 drawing, with x = 0 on the body's axis.

    ``gate_colors`` maps each active gate to one or two colours.
    """
    gate_notes = gate_notes or {}
    edge, fill, active = [], [], []

    def base(p, q):
        edge.append(_poly(geo.band_polygon(p, q, geo.BAND + 2.0), t["channel_edge"]))
        fill.append(_poly(geo.band_polygon(p, q, geo.BAND), t["channel_fill"]))

    for ch in D.CHANNELS:
        a, b = ch["gates"]
        if (a, b) in geo.INTEGRATION_CHANNELS:
            continue
        base(geo.G[a], geo.G[b])
        for (start, mid), g in zip(geo.channel_halves(a, b), (a, b)):
            if g in gate_colors:
                active.append(_band(start, _extend(start, mid, 0.6), gate_colors[g]))
    for g, (start, joint) in geo.INTEGRATION_ARMS.items():
        base(start, joint)
    base(geo.J10, geo.J34)
    for g, (start, joint) in geo.INTEGRATION_ARMS.items():
        if g in gate_colors:
            active.append(_band(start, _extend(start, joint), gate_colors[g]))
    # The spine between the two junctions lights only for a defined channel
    # that runs through it. Each half takes the colour of its nearer gate.
    spine: dict[str, list] = {"upper": [], "lower": []}
    for pair, pieces in geo.INTEGRATION_CHANNELS.items():
        if pair in defined_channels:
            for piece in pieces:
                spine[piece] += [gate_colors[g] for g in geo.SPINE_OWNER[piece] if g in pair]
    for piece, cols in spine.items():
        if cols:
            p, q = geo.INTEGRATION_SPINE[piece]
            active.append(_band(_extend(q, p), _extend(p, q), _merge(cols)))

    out = ["<g>", "".join(edge), "".join(fill), "".join(active), "</g>"]

    def tint(c):
        return t["mono"] if center_colors == "mono" else t["tints"][CENTER_TINT[c]]

    for c in D.CENTERS:
        state = center_states[c]
        f_, s_ = tint(c) if state == "defined" else (t["center_open"], t["center_stroke"])
        d = geo.rounded_polygon(geo.CENTER_SHAPES[c], 9.0)
        out.append(f'<path d="{d}" fill="{f_}" stroke="{s_}" stroke-width="1.6" '
                   f'stroke-linejoin="round"><title>{D.CENTER_NAMES[c]} center, {state}'
                   f"</title></path>")

    r = geo.BADGE_R
    for g, (x, y) in sorted(geo.G.items()):
        cols = gate_colors.get(g)
        c = D.GATE_CENTER[g]
        label = f"Gate {g}, {D.GATE_NAMES[g]}"
        if not cols:
            col = tint(c)[1] if center_states[c] == "defined" else t["gate_idle"]
            out.append(f"<g><title>{label}, inactive</title>"
                       + ts.text(x, y + 3.9, str(g), 11.2, font="num", fill=col, anchor="middle")
                       + "</g>")
            continue
        note = gate_notes.get(g, "active")
        parts = [f"<g><title>{label}, {note}</title>",
                 f'<circle cx="{_f(x)}" cy="{_f(y)}" r="{_f(r + 1.4)}" fill="{t["badge_ring"]}"/>']
        if len(cols) > 1:
            parts.append(f'<path d="M{_f(x)} {_f(y - r)}A{r} {r} 0 0 0 {_f(x)} {_f(y + r)}Z" '
                         f'fill="{cols[0]}"/>')
            parts.append(f'<path d="M{_f(x)} {_f(y - r)}A{r} {r} 0 0 1 {_f(x)} {_f(y + r)}Z" '
                         f'fill="{cols[1]}"/>')
        else:
            parts.append(f'<circle cx="{_f(x)}" cy="{_f(y)}" r="{r}" fill="{cols[0]}"/>')
        parts.append(ts.text(x, y + 4.0, str(g), 11.6, font="numbold", fill=t["badge_text"],
                             anchor="middle"))
        parts.append("</g>")
        out.append("".join(parts))
    return "".join(out)


def _natal_layers(chart: dict, t: dict):
    cmap = {"design": (t["design"],), "personality": (t["personality"],),
            "both": (t["design"], t["personality"])}
    colors = {int(g): cmap[v["activation"]] for g, v in chart["gates"].items()}
    notes = {int(g): v["activation"] if v["activation"] != "both"
             else "design and personality" for g, v in chart["gates"].items()}
    defined = {tuple(c["gates"]) for c in chart["channels"]}
    states = {c: v["state"] for c, v in chart["centers"].items()}
    return colors, defined, states, notes


# --------------------------------------------------------------------------
# side columns
# --------------------------------------------------------------------------
def _column(acts: dict, color: str, heading: str, x: float, y0: float, pitch: float,
            align: str, marks: bool = True) -> str:
    out = []
    for i, body in enumerate(ORDER):
        a = acts[body]
        y = y0 + i * pitch
        num = f'{a["gate"]}.{a["line"]}'
        w = ts.measure(num, 23, "num")
        if align == "right":
            tx, anchor, mx = x - 22, "end", x - 22 - w - 9
        else:
            tx, anchor, mx = x + 22, "start", x + 22 + w + 9
        retro = a["retrograde"] and body not in ("north_node", "south_node", "sun", "earth")
        out.append(f"<g><title>{heading} {D.BODY_NAMES[body]}: gate {a['gate']}, "
                   f"line {a['line']}, color {a['color']}, tone {a['tone']}, base {a['base']}"
                   f"{', retrograde' if retro else ''}</title>")
        out.append(_glyph(body, x, y - 7.5, 19, color))
        out.append(ts.text(tx, y, num, 23, font="num", fill=color, anchor=anchor))
        if marks and a.get("fixation"):
            out.append(_fix_mark(mx, y - 8, a["fixation"], color))
        out.append("</g>")
    return "".join(out)


def _fix_mark(x: float, y: float, kind: str, color: str) -> str:
    up = f"M{_f(x - 4)} {_f(y + 3)}L{_f(x)} {_f(y - 4)}L{_f(x + 4)} {_f(y + 3)}Z"
    dn = f"M{_f(x - 4)} {_f(y - 3)}L{_f(x)} {_f(y + 4)}L{_f(x + 4)} {_f(y - 3)}Z"
    if kind == "exalted":
        return f'<path d="{up}" fill="{color}"/>'
    if kind == "detriment":
        return (f'<path d="{dn}" fill="none" stroke="{color}" stroke-width="1.3" '
                f'stroke-linejoin="round"/>')
    return (f'<path d="M{_f(x - 4)} {_f(y)}L{_f(x)} {_f(y - 5)}L{_f(x + 4)} {_f(y)}'
            f'L{_f(x)} {_f(y + 5)}Z" fill="{color}"/>')


# --------------------------------------------------------------------------
# page furniture
# --------------------------------------------------------------------------
W = 1000.0
M = 56.0            # page margin
COL_L, COL_R = 66.0, W - 66.0
PITCH = 56.0


def _segments(x: float, y: float, segs, t: dict, anchor: str = "start", gap: float = 9.0) -> str:
    """Runs of text in different fonts on one baseline: (text, size, font, colour key)."""
    widths = [ts.measure(s, size, font) for s, size, font, _ in segs]
    total = sum(widths) + gap * (len(segs) - 1)
    cur = x - total if anchor == "end" else x
    out = []
    for (s, size, font, col), w in zip(segs, widths):
        out.append(ts.text(cur, y, s, size, font=font, fill=t[col]))
        cur += w + gap
    return "".join(out)


def _rule(y: float, t: dict) -> str:
    return f'<path d="M{_f(M)} {_f(y)}H{_f(W - M)}" stroke="{t["rule"]}" stroke-width="1.5"/>'


def _header(t: dict, title: str, sub: str, right, right_sub: str) -> tuple[str, float]:
    y = 70.0
    out = [ts.text(M, y, title, 40, font="semibold", fill=t["ink"]),
           _segments(W - M, y, right, t, anchor="end", gap=11),
           ts.text(M, y + 31, sub, 16, fill=t["muted"]),
           ts.text(W - M, y + 31, right_sub, 16, fill=t["muted"], anchor="end")]
    return "".join(out), y + 31 + 26


def _footer(t: dict, y: float, long: bool, calc: dict | None, show: bool) -> tuple[str, float]:
    if not show:
        return "", y
    out = [_rule(y + 14, t)]
    y += 44
    for ln in ts.wrap(D.DISCLAIMER if long else D.DISCLAIMER_SHORT, 13.5, W - 2 * M):
        out.append(ts.text(M, y, ln, 13.5, fill=t["muted"]))
        y += 20
    if long and calc:
        out.append(ts.text(M, y + 4, f'Positions: {calc.get("ephemeris", "")}. '
                           f'{calc.get("node", "true").title()} node. Design at '
                           f'{calc.get("design_arc_degrees", 88):g}° of solar arc.',
                           13.5, fill=t["faint"]))
        y += 24
    return "".join(out), y


def _wrap_svg(t: dict, session, parts: list[str], height: float, label: str,
              background: bool) -> str:
    label = html.escape(label)
    bg = f'<rect width="{_f(W)}" height="{_f(height)}" fill="{t["paper"]}"/>' if background else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_f(W)} {_f(height)}" '
            f'width="{_f(W)}" height="{_f(height)}" role="img" aria-label="{label}">'
            f"<title>{label}</title><desc>{html.escape(D.DISCLAIMER)}</desc>"
            f'{session.defs()}{bg}{"".join(parts)}</svg>')


def _when(iso: str) -> str:
    return iso[:16].replace("T", " ") + " UTC"


def _theme(theme: str) -> dict:
    if theme not in THEMES:
        raise ValueError("theme must be 'light' or 'dark'")
    return THEMES[theme]


# --------------------------------------------------------------------------
# natal chart
# --------------------------------------------------------------------------
def render_svg(chart: dict, *, name: str | None = None, subtitle: str | None = None,
               theme: str = "light", layout: str = "full",
               center_colors: str = "traditional", disclaimer: bool = True,
               background: bool = True) -> str:
    """Render a natal chart. ``layout`` is 'full' (header, graph, summary) or 'graph'."""
    t = _theme(theme)
    if layout not in ("full", "graph"):
        raise ValueError("layout must be 'full' or 'graph'")
    if center_colors not in ("traditional", "mono"):
        raise ValueError("center_colors must be 'traditional' or 'mono'")
    with ts.Session() as session:
        parts: list[str] = []
        cx = W / 2
        v = chart["variables"]
        if layout == "full":
            head, y = _header(
                t, name or "Bodygraph",
                subtitle or f'Born {_when(chart["birth"]["utc"])}',
                [(chart["type"], 25, "medium", "ink"),
                 (chart["profile"]["notation"], 25, "numbold", "ink")],
                chart["authority"] + " authority")
            parts.append(head)
        else:
            y = 16.0
        gy = y + 14
        head_y = gy + 28
        parts.append(ts.text(COL_L - 9, head_y, "Design", 19, font="semibold", fill=t["design"]))
        parts.append(ts.text(COL_R + 9, head_y, "Personality", 19, font="semibold",
                             fill=t["personality"], anchor="end"))
        parts.append(ts.text(COL_L - 9, head_y + 21, _when(chart["design"]["utc"]), 13,
                             fill=t["muted"], tabular=True))
        parts.append(ts.text(COL_R + 9, head_y + 21, _when(chart["birth"]["utc"]), 13,
                             fill=t["muted"], anchor="end", tabular=True))
        col_y = gy + 140
        acts = chart["activations"]
        parts.append(_column(acts["design"], t["design"], "Design", COL_L, col_y, PITCH, "left"))
        parts.append(_column(acts["personality"], t["personality"], "Personality", COL_R,
                             col_y, PITCH, "right"))
        if any(a.get("fixation") for imp in acts.values() for a in imp.values()):
            ly = col_y + 12 * PITCH + 46
            parts.append(_fix_mark(COL_L - 4, ly - 5, "exalted", t["muted"]))
            parts.append(ts.text(COL_L + 7, ly, "exalted", 13, fill=t["muted"]))
            parts.append(_fix_mark(COL_L + 66, ly - 5, "detriment", t["muted"]))
            parts.append(ts.text(COL_L + 77, ly, "detriment", 13, fill=t["muted"]))
            if any(a.get("fixation") == "juxtaposed" for imp in acts.values()
                   for a in imp.values()):
                parts.append(_fix_mark(COL_L + 148, ly - 5, "juxtaposed", t["muted"]))
                parts.append(ts.text(COL_L + 159, ly, "both", 13, fill=t["muted"]))

        ay = gy + 44
        for key, dx, dy, col in (("determination", -118, 0, t["design"]),
                                 ("environment", -118, 30, t["design"]),
                                 ("motivation", 118, 0, t["personality"]),
                                 ("perspective", 118, 30, t["personality"])):
            parts.append(f'<g><title>{key.title()}: {v[key]["name"]}, {v[key]["orientation"]}'
                         f"</title>" + _arrow(cx + dx, ay + dy, v[key]["orientation"], col)
                         + "</g>")

        colors, defined, states, notes = _natal_layers(chart, t)
        parts.append(f'<g transform="translate({_f(cx)} {_f(gy)})">'
                     + bodygraph_group(t, colors, defined, states, center_colors, notes) + "</g>")
        y = gy + geo.HEIGHT

        if layout == "full":
            y += 34
            parts.append(_rule(y, t))
            y += 42
            cross = chart["incarnation_cross"]
            facts = [
                ("Type", [(chart["type"], "medium")]),
                ("Strategy", [(chart["strategy"], "medium")]),
                ("Authority", [(chart["authority"], "medium")]),
                ("Profile", [(chart["profile"]["notation"], "numbold"),
                             (chart["profile"]["name"], "medium")]),
                ("Definition", [(chart["definition"], "medium")]),
                ("Signature", [(chart["signature"], "medium")]),
                ("Not-self theme", [(chart["not_self_theme"], "medium")]),
                ("Incarnation cross", [(cross["name"] if cross else "None", "medium")]),
                ("Cross gates", [(x, "numbold") for x in
                                 (cross["notation"].split(" | ") if cross else [""])]),
                ("Cognition", [(v["cognition"], "medium")]),
            ]
            col_w = (W - 2 * M - 40) / 2
            yy = [y, y]
            for i, (k, segs) in enumerate(facts):
                c = 0 if i < 5 else 1
                x0 = M + c * (col_w + 40)
                parts.append(ts.text(x0, yy[c], k, 14.5, fill=t["muted"]))
                if len(segs) == 1:
                    lines = ts.wrap(segs[0][0], 17, col_w - 150, segs[0][1])
                    for j, ln in enumerate(lines):
                        parts.append(ts.text(x0 + 150, yy[c] + j * 23, ln, 17, font=segs[0][1],
                                             fill=t["ink"]))
                    yy[c] += 23 * max(len(lines), 1) + 13
                else:
                    parts.append(_segments(x0 + 150, yy[c],
                                           [(s, 17, f, "ink") for s, f in segs], t, gap=14))
                    yy[c] += 36
            y = max(yy) + 12

            parts.append(ts.text(M, y, "Variables", 14.5, fill=t["muted"]))
            cell = (W - 2 * M - 150) / 4
            for i, (key, col) in enumerate((("determination", t["design"]),
                                            ("environment", t["design"]),
                                            ("motivation", t["personality"]),
                                            ("perspective", t["personality"]))):
                x0 = M + 150 + i * cell
                parts.append(_arrow(x0 + 11, y - 6, v[key]["orientation"], col, 22))
                parts.append(ts.text(x0 + 32, y, v[key]["name"], 17, font="medium", fill=t["ink"]))
                parts.append(ts.text(x0 + 32, y + 20, key.title(), 13.5, fill=t["muted"]))
            y += 58

            parts.append(ts.text(M, y, "Channels", 14.5, fill=t["muted"]))
            body, y = _channel_list(t, chart["channels"], y,
                                    "None. All nine centers are open.")
            parts.append(body)

        foot, y = _footer(t, y, layout == "full", chart.get("calculation"), disclaimer)
        parts.append(foot)
        label = (f'Human Design bodygraph{" for " + name if name else ""}: {chart["type"]}, '
                 f'profile {chart["profile"]["notation"]}, {chart["authority"]} authority, '
                 f'{chart["definition"].lower()}.')
        return _wrap_svg(t, session, parts, y + 34, label, background)


def _channel_list(t: dict, channels: list[dict], y: float, empty: str,
                  suffix=lambda ch: "") -> tuple[str, float]:
    out = []
    if not channels:
        out.append(ts.text(M + 150, y, empty, 16, fill=t["ink"]))
        return "".join(out), y + 37
    per = 3
    cw = (W - 2 * M - 150) / per
    for i, ch in enumerate(channels):
        x0 = M + 150 + (i % per) * cw
        yy = y + (i // per) * 27
        out.append(ts.text(x0, yy, ch["id"], 17, font="numbold", fill=t["ink"]))
        out.append(ts.text(x0 + 54, yy, ch["name"] + suffix(ch), 16, fill=t["ink"]))
    return "".join(out), y + 27 * math.ceil(len(channels) / per) + 10


# --------------------------------------------------------------------------
# connection chart for two people
# --------------------------------------------------------------------------
def render_composite_svg(a: dict, b: dict, comp: dict, *, name_a: str = "Person A",
                         name_b: str = "Person B", theme: str = "light",
                         center_colors: str = "traditional", disclaimer: bool = True,
                         background: bool = True) -> str:
    t = _theme(theme)
    ca, cb = t["person_a"], t["person_b"]
    with ts.Session() as session:
        parts: list[str] = []
        head, y = _header(
            t, f"{name_a} and {name_b}", "Connection chart",
            [("Centers defined together", 18, "regular", "muted"),
             (comp["connection_theme"], 25, "numbold", "ink")],
            comp["definition"])
        parts.append(head)
        gy = y + 14
        for chart, col, nm, x, anchor, align in ((a, ca, name_a, COL_L, "start", "left"),
                                                 (b, cb, name_b, COL_R, "end", "right")):
            edge = x - 9 if align == "left" else x + 9
            parts.append(ts.text(edge, gy + 28, nm, 19, font="semibold", fill=col, anchor=anchor))
            parts.append(ts.text(edge, gy + 49,
                                 f'{chart["type"]} {chart["profile"]["notation"]}', 13.5,
                                 fill=t["muted"], anchor=anchor))
            merged = {}
            for body in ORDER:          # personality gate.line; design shown in the graph
                merged[body] = chart["activations"]["personality"][body]
            parts.append(_column(merged, col, nm, x, gy + 140, PITCH, align, marks=False))
        ga, gb = {int(g) for g in a["gates"]}, {int(g) for g in b["gates"]}
        colors = {g: ((ca, cb) if g in ga and g in gb else (ca,) if g in ga else (cb,))
                  for g in ga | gb}
        notes = {g: (f"{name_a} and {name_b}" if g in ga and g in gb else
                     name_a if g in ga else name_b) for g in ga | gb}
        defined = {tuple(int(x) for x in ch["id"].split("-")) for ch in comp["channels"]}
        states = {c: ("defined" if c in comp["defined_centers"] else
                      "undefined" if any(g in colors for g in D.CENTER_GATES[c]) else "open")
                  for c in D.CENTERS}
        parts.append(f'<g transform="translate({_f(W / 2)} {_f(gy)})">'
                     + bodygraph_group(t, colors, defined, states, center_colors, notes) + "</g>")
        y = gy + geo.HEIGHT + 34
        parts.append(_rule(y, t))
        y += 42
        labels = (("electromagnetic", "Electromagnetic", "each person brings one gate"),
                  ("compromise", "Compromise", "one has the channel, the other one gate"),
                  ("dominance", "Dominance", "one person has the whole channel"),
                  ("companionship", "Companionship", "both have the whole channel"))
        for key, title, _hint in labels:
            group = [c for c in comp["channels"] if c["connection"] == key]
            parts.append(ts.text(M, y, title, 14.5, fill=t["muted"]))
            body, y = _channel_list(t, group, y, "None")
            parts.append(body)
        note = "Side columns list each person's Personality activations."
        parts.append(ts.text(M, y + 6, note, 13.5, fill=t["faint"]))
        y += 20
        foot, y = _footer(t, y, True, a.get("calculation"), disclaimer)
        parts.append(foot)
        return _wrap_svg(t, session, parts, y + 34,
                         f"Human Design connection chart for {name_a} and {name_b}.", background)


# --------------------------------------------------------------------------
# transits over a natal chart
# --------------------------------------------------------------------------
def render_transit_svg(natal: dict, transit: dict, overlay: dict, *, name: str | None = None,
                       theme: str = "light", center_colors: str = "traditional",
                       disclaimer: bool = True, background: bool = True) -> str:
    t = _theme(theme)
    tc = t["transit"]
    with ts.Session() as session:
        parts: list[str] = []
        head, y = _header(
            t, name or "Bodygraph", f'Transits for {_when(transit["utc"])}',
            [(natal["type"], 25, "medium", "ink"),
             (natal["profile"]["notation"], 25, "numbold", "ink")],
            f'{len(overlay["completed_channels"])} channels completed by transit')
        parts.append(head)
        gy = y + 14
        parts.append(ts.text(COL_L - 9, gy + 28, "Transit", 19, font="semibold", fill=tc))
        parts.append(ts.text(COL_L - 9, gy + 49, _when(transit["utc"]), 13, fill=t["muted"],
                             tabular=True))
        parts.append(ts.text(COL_R + 9, gy + 28, "Personality", 19, font="semibold",
                             fill=t["personality"], anchor="end"))
        parts.append(ts.text(COL_R + 9, gy + 49, _when(natal["birth"]["utc"]), 13,
                             fill=t["muted"], anchor="end", tabular=True))
        parts.append(_column(transit["activations"], tc, "Transit", COL_L, gy + 140, PITCH,
                             "left", marks=False))
        parts.append(_column(natal["activations"]["personality"], t["personality"],
                             "Personality", COL_R, gy + 140, PITCH, "right", marks=False))
        colors, defined, states, notes = _natal_layers(natal, t)
        for g in transit["gates"]:
            g = int(g)
            if g not in colors:
                colors[g], notes[g] = (tc,), "transit"
            else:
                notes[g] += " and transit"
        for ch in overlay["completed_channels"]:
            defined.add(tuple(int(x) for x in ch["id"].split("-")))
        for c in overlay["temporarily_defined_centers"]:
            states[c] = "defined"
        for c in D.CENTERS:
            if states[c] == "open" and any(g in colors for g in D.CENTER_GATES[c]):
                states[c] = "undefined"
        parts.append(f'<g transform="translate({_f(W / 2)} {_f(gy)})">'
                     + bodygraph_group(t, colors, defined, states, center_colors, notes) + "</g>")
        y = gy + geo.HEIGHT + 34
        parts.append(_rule(y, t))
        y += 42
        parts.append(ts.text(M, y, "Completed now", 14.5, fill=t["muted"]))
        body, y = _channel_list(t, overlay["completed_channels"], y,
                                "The current sky completes no channels in this chart.")
        parts.append(body)
        parts.append(ts.text(M, y, "Natal channels", 14.5, fill=t["muted"]))
        body, y = _channel_list(t, natal["channels"], y, "None")
        parts.append(body)
        foot, y = _footer(t, y, True, natal.get("calculation"), disclaimer)
        parts.append(foot)
        return _wrap_svg(t, session, parts, y + 34,
                         f'Human Design transit chart{" for " + name if name else ""}.',
                         background)
