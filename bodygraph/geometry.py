"""Bodygraph geometry, drawn from scratch on a 600 x 910 grid.

The vertical axis of the body is x = 0. Every channel is a band along a cubic
curve between two gate anchors. The four-armed Integration group on the left
shares one spine between the Throat and the Spleen.
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


# ---- channel paths ---------------------------------------------------------
# Every channel is a cubic Bezier from one gate anchor to the other. Short
# channels on the axis are straight. Long ones leave each center square to
# its edge and arc around whatever lies between.
def _unit(v):
    n = math.hypot(*v)
    return (v[0] / n, v[1] / n)


def _edge_normal(a, b):
    """Unit normal of edge a->b pointing out of the triangle (left of travel)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    return _unit((dy, -dx))


_SPL_UP = _edge_normal(SPL_TOP, SPL_TIP)      # out of the spleen's upper edge
_SPL_DN = _edge_normal(SPL_TIP, SPL_BOT)      # out of its lower edge
_SOL_UP = (-_SPL_UP[0], _SPL_UP[1])
_SOL_DN = (-_SPL_DN[0], _SPL_DN[1])
LEFT, RIGHT, UP, DOWN = (-1.0, 0.0), (1.0, 0.0), (0.0, -1.0), (0.0, 1.0)


def _curve(p0, p3, d0=None, l0=0.0, d3=None, l3=0.0):
    """Cubic from p0 to p3. It leaves p0 along d0 and reaches p3 from d3."""
    c1 = (p0[0] + d0[0] * l0, p0[1] + d0[1] * l0) if d0 else _lerp(p0, p3, 1 / 3)
    c2 = (p3[0] + d3[0] * l3, p3[1] + d3[1] * l3) if d3 else _lerp(p0, p3, 2 / 3)
    return (p0, c1, c2, p3)


def bezier(curve, t):
    p0, c1, c2, p3 = curve
    u = 1.0 - t
    a, b, c, d = u * u * u, 3 * u * u * t, 3 * u * t * t, t * t * t
    return (a * p0[0] + b * c1[0] + c * c2[0] + d * p3[0],
            a * p0[1] + b * c1[1] + c * c2[1] + d * p3[1])


def bezier_tangent(curve, t):
    p0, c1, c2, p3 = curve
    u = 1.0 - t
    return _unit((3 * u * u * (c1[0] - p0[0]) + 6 * u * t * (c2[0] - c1[0]) + 3 * t * t * (p3[0] - c2[0]),
                  3 * u * u * (c1[1] - p0[1]) + 6 * u * t * (c2[1] - c1[1]) + 3 * t * t * (p3[1] - c2[1])))


def sample(curve, t0=0.0, t1=1.0, steps=None):
    """Points along the curve from t0 to t1. Straight curves need two."""
    p0, c1, c2, p3 = curve
    flat = (abs((c1[0] - p0[0]) * (p3[1] - p0[1]) - (c1[1] - p0[1]) * (p3[0] - p0[0])) < 1e-6
            and abs((c2[0] - p0[0]) * (p3[1] - p0[1]) - (c2[1] - p0[1]) * (p3[0] - p0[0])) < 1e-6)
    if steps is None:
        steps = 1 if flat else max(4, int(28 * abs(t1 - t0)))
    return [bezier(curve, t0 + (t1 - t0) * i / steps) for i in range(steps + 1)]


CURVES: dict[tuple[int, int], tuple] = {}


def _link(a, b, d0=None, l0=0.0, d3=None, l3=0.0):
    CURVES[(a, b)] = _curve(G[a], G[b], d0, l0, d3, l3)


# straight runs on and near the axis
for _a, _b in ((61, 24), (63, 4), (47, 64), (17, 62), (23, 43), (11, 56), (7, 31), (1, 8),
               (13, 33), (5, 15), (2, 14), (29, 46), (42, 53), (3, 60), (9, 52),
               (27, 50), (6, 59), (37, 40)):
    _link(_a, _b)
# throat out to the spleen and the solar plexus
_link(16, 48, LEFT, 150, _SPL_UP, 130)
_link(35, 36, RIGHT, 150, _SOL_UP, 130)
_link(12, 22, RIGHT, 118, _SOL_UP, 108)
# heart
_link(21, 45, UP, 60, RIGHT, 62)
_link(25, 51, RIGHT, 34, UP, 30)
_link(26, 44, (-0.97, -0.24), 120, _SPL_UP, 78)
# spleen and solar plexus down to the root
_link(32, 54, _SPL_DN, 46, LEFT, 70)
_link(28, 38, _SPL_DN, 62, LEFT, 96)
_link(18, 58, _SPL_DN, 78, LEFT, 122)
_link(19, 49, RIGHT, 70, _SOL_DN, 46)
_link(39, 55, RIGHT, 96, _SOL_DN, 62)
_link(30, 41, _SOL_DN, 78, RIGHT, 122)

# ---- Integration group -----------------------------------------------------
# One spine from gate 20 (Throat) to gate 57 (Spleen). Gate 10 joins it from
# the G center and flows down toward 57. Gate 34 rises from the Sacral and
# flows up toward 20. Both merge along the spine's tangent, with no corner.
SPINE = _curve(G[20], G[57], LEFT, 118, _SPL_UP, 108)
T10, T34 = 0.66, 0.82
TMID = (T10 + T34) / 2
J10, J34 = bezier(SPINE, T10), bezier(SPINE, T34)
_t10, _t34 = bezier_tangent(SPINE, T10), bezier_tangent(SPINE, T34)
ARM10 = _curve(G[10], J10, LEFT, 78, (-_t10[0], -_t10[1]), 26)
ARM34 = _curve(G[34], J34, LEFT, 104, _t34, 30)

# arm of each gate as (curve, t from, t to), starting at the gate
INTEGRATION_ARMS = {
    20: (SPINE, 0.0, T10), 57: (SPINE, 1.0, T34),
    10: (ARM10, 0.0, 1.0), 34: (ARM34, 0.0, 1.0),
}
INTEGRATION_SPINE = {"upper": (SPINE, T10, TMID), "lower": (SPINE, T34, TMID)}
INTEGRATION_CHANNELS = {
    (10, 20): [], (34, 57): [],
    (20, 57): ["upper", "lower"], (20, 34): ["upper", "lower"],
    (10, 57): ["upper", "lower"], (10, 34): ["upper", "lower"],
}
SPINE_OWNER = {"upper": (20, 10), "lower": (57, 34)}

assert len(CURVES) + len(INTEGRATION_CHANNELS) == 36, len(CURVES)


def channel_halves(a: int, b: int):
    """Two pieces, one per gate, meeting at the middle of a plain channel."""
    curve = CURVES[(a, b)]
    return (curve, 0.0, 0.5), (curve, 1.0, 0.5)


def offset_points(points, offset):
    """The polyline shifted sideways by ``offset`` px (left of travel is negative)."""
    out = []
    n = len(points)
    for i, (x, y) in enumerate(points):
        ax, ay = points[max(i - 1, 0)]
        bx, by = points[min(i + 1, n - 1)]
        dx, dy = bx - ax, by - ay
        m = math.hypot(dx, dy) or 1.0
        out.append((x - dy / m * offset, y + dx / m * offset))
    return out


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


# ---- figure ----------------------------------------------------------------
# A plain standing figure behind the graph: head, neck, shoulders, torso.
FIGURE = (
    "M0 -12C62 -12 104 30 104 100C104 150 88 194 64 222C60 246 70 258 94 266"
    "C182 290 256 322 286 396C306 462 314 560 316 660L316 840C316 886 290 912 244 912"
    "L-244 912C-290 912 -316 886 -316 840L-316 660C-314 560 -306 462 -286 396"
    "C-256 322 -182 290 -94 266C-70 258 -60 246 -64 222C-88 194 -104 150 -104 100"
    "C-104 30 -62 -12 0 -12Z"
)
