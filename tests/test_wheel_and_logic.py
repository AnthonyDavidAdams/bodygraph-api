import random
from datetime import datetime, timedelta, timezone

from bodygraph import data as D
from bodygraph.chart import _authority, _components, _type, build_chart, composite
from bodygraph.wheel import (CELL_DEG, GATE_ORDER, activation, gate_span, opposite_gate)


def test_wheel_layout():
    assert sorted(GATE_ORDER) == list(range(1, 65))
    assert gate_span(41)[0] == 302.0                      # 2 deg Aquarius
    assert abs(gate_span(25)[0] - 358.25) < 1e-9          # 28 deg 15' Pisces
    assert activation(302.0).gate_line == "41.1"
    assert activation(301.999999).gate_line == "60.6"
    assert activation(0.0).gate == 25 and activation(10.0).gate == 21
    assert activation(19.2).gate_line == "51.5"               # Ra Uru Hu's Sun
    for g in GATE_ORDER:
        assert opposite_gate(opposite_gate(g)) == g


def test_every_cell_boundary_is_exact():
    """69,120 base cells. The first point of each belongs to that cell."""
    for cell in range(69120):
        want = (GATE_ORDER[cell // 1080], cell // 180 % 6 + 1, cell // 30 % 6 + 1,
                cell // 5 % 6 + 1, cell % 5 + 1)
        for frac in (0.0, 0.5, 0.999):
            a = activation((302.0 + (cell + frac) * CELL_DEG) % 360.0)
            assert want == (a.gate, a.line, a.color, a.tone, a.base), (cell, frac)


def test_tables_are_complete():
    assert len(D.CHANNELS) == 36 and len(D.CROSSES) == 192
    assert {g for c in D.CHANNELS for g in c["gates"]} == set(range(1, 65))
    assert sum(len(v) for v in D.CENTER_GATES.values()) == 64
    assert D.GATE_CENTER[52] == "root"                    # hdkit has this as throat
    for c in D.CHANNELS:
        assert c["centers"] == [D.GATE_CENTER[c["gates"][0]], D.GATE_CENTER[c["gates"][1]]]


def _ch(*ids):
    want = {tuple(int(x) for x in i.split("-")) for i in ids}
    return [c for c in D.CHANNELS if tuple(c["gates"]) in want]


def test_type_and_authority_rules():
    cases = [
        ([], "Reflector", "lunar"),
        (["24-61"], "Projector", "mental"),
        (["7-31"], "Projector", "self_projected"),
        (["25-51"], "Projector", "ego_projected"),
        (["21-45"], "Manifestor", "ego_manifested"),
        (["25-51", "7-31"], "Manifestor", "ego_manifested"),     # heart to throat through G
        (["26-44", "10-57", "10-20"], "Manifestor", "splenic"),  # heart, spleen, G, throat
        (["18-58", "16-48"], "Manifestor", "splenic"),           # root motor through spleen
        (["18-58"], "Projector", "splenic"),
        (["3-60"], "Generator", "sacral"),
        (["20-34"], "Manifesting Generator", "sacral"),
        (["2-14", "1-8"], "Manifesting Generator", "sacral"),
        (["3-60", "12-22"], "Manifesting Generator", "emotional"),
        (["6-59"], "Generator", "emotional"),
        (["3-60", "7-31"], "Generator", "sacral"),               # throat defined, no motor link
        (["35-36"], "Manifestor", "emotional"),
    ]
    for ids, hd_type, auth in cases:
        comp = _components(_ch(*ids))
        assert _type(comp) == hd_type, ids
        assert _authority(comp, hd_type) == auth, ids


def test_cross_gates_follow_from_geometry():
    """The table's four gates must match what the sky produces, for any chart."""
    rng = random.Random(7)
    seen = set()
    for _ in range(400):
        t = datetime(1900, 1, 1, tzinfo=timezone.utc) + timedelta(
            minutes=rng.randrange(0, 150 * 365 * 1440))
        c = build_chart(t)
        x = c["incarnation_cross"]
        assert c["profile"]["valid"] and x["table_gates_match"], (t, x)
        assert abs(c["design"]["solar_arc_degrees"] - 88.0) < 1e-6
        seen.add(c["type"])
        groups = c["definition_groups"]
        assert sorted(sum(groups, [])) == sorted(c["defined_centers"])
    assert seen >= {"Generator", "Manifesting Generator", "Projector", "Manifestor"}


def test_composite_classification():
    a = build_chart(datetime(1954, 1, 29, 10, 30, tzinfo=timezone.utc))
    b = build_chart(datetime(1948, 4, 9, 5, 14, tzinfo=timezone.utc))
    comp = composite(a, b)
    kinds = {c["id"]: c["connection"] for c in comp["channels"]}
    assert kinds["19-49"] == "compromise" and kinds["25-51"] == "dominance"
    assert kinds["26-44"] == "electromagnetic"
    assert composite(a, a)["connection_counts"] == {"companionship": len(a["channels"])}


def test_channel_geometry_is_complete_and_joined():
    from bodygraph import geometry as geo
    pairs = {tuple(sorted(k)) for k in geo.CURVES} | set(geo.INTEGRATION_CHANNELS)
    assert pairs == {tuple(c["gates"]) for c in D.CHANNELS}
    for (a, b), curve in geo.CURVES.items():
        assert curve[0] == geo.G[a] and curve[3] == geo.G[b]
    # each arm of the Integration group starts at its gate and ends on the spine
    for gate, (curve, t0, t1) in geo.INTEGRATION_ARMS.items():
        start, end = geo.bezier(curve, t0), geo.bezier(curve, t1)
        assert max(abs(start[0] - geo.G[gate][0]), abs(start[1] - geo.G[gate][1])) < 1e-9
        on_spine = min(abs(end[0] - j[0]) + abs(end[1] - j[1]) for j in (geo.J10, geo.J34))
        assert on_spine < 1e-9
