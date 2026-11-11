"""Bodygraph geometry, drawn from scratch on a 600 x 910 grid.

The vertical axis of the body is x = 0. Every channel is a straight band
between two gate anchors, except the four-armed Integration group on the
left, which shares one spine between the Throat and the Spleen.
"""
from __future__ import annotations

import math

WIDTH, HEIGHT = 600.0, 910.0
X0 = 300.0          # add to every x below to place the axis
P = 28.0            # spacing of the three parallel channels on the axis
BADGE_R = 10.0
BAND = 9.0          # channel width


def _lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def _edge_points(a, b, inset, stops):
    """Points along edge a->b, pushed ``inset`` px toward the triangle's inside
    (the right-hand side of the direction of travel)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = math.hypot(dx, dy)
    nx, ny = -dy / n, dx / n
    return [(a[0] + dx * t + nx * inset, a[1] + dy * t + ny * inset) for t in stops]


# ---- centers ---------------------------------------------------------------
# kind: 'poly' with vertices, drawn with rounded corners.
SPL_TOP, SPL_BOT, SPL_TIP = (-278.0, 558.0), (-278.0, 742.0), (-140.0, 650.0)
SOL_TOP, SOL_BOT, SOL_TIP = (278.0, 558.0), (278.0, 742.0), (140.0, 650.0)

CENTER_SHAPES: dict[str, list[tuple[float, float]]] = {
    "head": [(0, 12), (64, 110), (-64, 110)],
    "ajna": [(-64, 150), (64, 150), (0, 248)],
    "throat": [(-58, 276), (58, 276), (58, 392), (-58, 392)],
    "g": [(0, 418), (64, 482), (0, 546), (-64, 482)],
    "heart": [(112, 506), (172, 600), (52, 600)],
    "spleen": [SPL_TOP, SPL_TIP, SPL_BOT],
    "solar_plexus": [SOL_TOP, SOL_BOT, SOL_TIP],
    "sacral": [(-58, 622), (58, 622), (58, 738), (-58, 738)],
    "root": [(-58, 774), (58, 774), (58, 890), (-58, 890)],
}
CENTER_LABEL_AT = {
    "head": (0, 62), "ajna": (0, 192), "throat": (0, 334), "g": (0, 482),
    "heart": (112, 574), "spleen": (-246, 650), "solar_plexus": (246, 650),
    "sacral": (0, 680), "root": (0, 838),
}

# ---- gate anchors ----------------------------------------------------------
G: dict[int, tuple[float, float]] = {}
# head, base row
G[64], G[61], G[63] = (-P, 93), (0, 93), (P, 93)
# ajna
G[47], G[24], G[4] = (-P, 167), (0, 167), (P, 167)
G[17], G[11], G[43] = (-20, 199), (20, 199), (0, 225)
# throat
G[62], G[23], G[56] = (-P, 293), (0, 293), (P, 293)
G[16], G[20] = (-41, 319), (-41, 349)
G[35], G[12], G[45] = (41, 314), (41, 337), (41, 360)
G[31], G[8], G[33] = (-P, 375), (0, 375), (P, 375)
# g
G[1] = (0, 438)
G[7], G[13] = (-P, 462), (P, 462)
G[10], G[25] = (-45, 484), (45, 484)
G[15], G[46] = (-P, 504), (P, 504)
G[2] = (0, 526)
# heart
G[21] = (112, 532)
G[51] = (88, 560)
G[26], G[40] = (76, 585), (148, 585)
# sacral
G[5], G[14], G[29] = (-P, 639), (0, 639), (P, 639)
G[34], G[27] = (-41, 666), (-41, 700)
G[59] = (41, 690)
G[42], G[3], G[9] = (-P, 721), (0, 721), (P, 721)
# root
G[53], G[60], G[52] = (-P, 791), (0, 791), (P, 791)
G[54], G[38], G[58] = (-41, 817), (-41, 842), (-41, 867)
G[19], G[39], G[41] = (41, 817), (41, 842), (41, 867)
# spleen: upper edge runs top -> tip, lower edge tip -> bottom
_up = _edge_points(SPL_TOP, SPL_TIP, 15, (0.26, 0.45, 0.64))
G[48], G[57], G[44] = _up
G[50] = (SPL_TIP[0] - 30, SPL_TIP[1])
_lo = _edge_points(SPL_TIP, SPL_BOT, 15, (0.36, 0.55, 0.74))
G[32], G[28], G[18] = _lo
# solar plexus mirrors the spleen
for _a, _b in ((36, 48), (22, 57), (37, 44), (6, 50), (49, 32), (55, 28), (30, 18)):
    G[_a] = (-G[_b][0], G[_b][1])

assert len(G) == 64


def _line_x_at(a, b, y):
    t = (y - a[1]) / (b[1] - a[1])
    return a[0] + (b[0] - a[0]) * t


# ---- Integration group -----------------------------------------------------
# One spine from gate 20 (Throat) to gate 57 (Spleen). Gate 10 joins it by a
# level arm from the G center, gate 34 by a rising arm from the Sacral.
J10 = (_line_x_at(G[20], G[57], G[10][1]), G[10][1])
_J34_Y = 566.0
J34 = (_line_x_at(G[20], G[57], _J34_Y), _J34_Y)
JMID = _lerp(J10, J34, 0.5)

# arm of each gate, and the spine pieces a channel lights between its arms
INTEGRATION_ARMS = {
    20: (G[20], J10), 10: (G[10], J10), 34: (G[34], J34), 57: (G[57], J34),
}
INTEGRATION_SPINE = {"upper": (J10, JMID), "lower": (JMID, J34)}
INTEGRATION_CHANNELS = {
    (10, 20): [], (34, 57): [],
    (20, 57): ["upper", "lower"], (20, 34): ["upper", "lower"],
    (10, 57): ["upper", "lower"], (10, 34): ["upper", "lower"],
}
SPINE_OWNER = {"upper": (20, 10), "lower": (57, 34)}


def channel_halves(a: int, b: int):
    """Two segments, one per gate, meeting at the middle of a plain channel."""
    mid = _lerp(G[a], G[b], 0.5)
    return (G[a], mid), (G[b], mid)


def band_polygon(p, q, width=BAND, offset=0.0):
    """Corner points of a band of ``width`` centered ``offset`` px off p->q."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    n = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / n, dx / n
    h = width / 2.0
    return [
        (p[0] + nx * (offset - h), p[1] + ny * (offset - h)),
        (q[0] + nx * (offset - h), q[1] + ny * (offset - h)),
        (q[0] + nx * (offset + h), q[1] + ny * (offset + h)),
        (p[0] + nx * (offset + h), p[1] + ny * (offset + h)),
    ]


def rounded_polygon(points, radius):
    """SVG path for a polygon with circular-arc corners."""
    n = len(points)
    out = []
    for i in range(n):
        p0, p1, p2 = points[i - 1], points[i], points[(i + 1) % n]
        v1 = (p0[0] - p1[0], p0[1] - p1[1])
        v2 = (p2[0] - p1[0], p2[1] - p1[1])
        l1, l2 = math.hypot(*v1), math.hypot(*v2)
        ang = math.acos(max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (l1 * l2))))
        d = min(radius / math.tan(ang / 2.0), l1 / 2.0, l2 / 2.0)
        r = d * math.tan(ang / 2.0)
        a = (p1[0] + v1[0] / l1 * d, p1[1] + v1[1] / l1 * d)
        b = (p1[0] + v2[0] / l2 * d, p1[1] + v2[1] / l2 * d)
        cross = v1[0] * v2[1] - v1[1] * v2[0]
        sweep = 1 if cross < 0 else 0
        out.append(f"{'M' if i == 0 else 'L'}{a[0]:.2f} {a[1]:.2f}"
                   f"A{r:.2f} {r:.2f} 0 0 {sweep} {b[0]:.2f} {b[1]:.2f}")
    return "".join(out) + "Z"
