"""Build bodygraph/tables.json from four independent open-source projects and
report every place where they disagree.

Sources (all MIT licensed):
  pyhd                         github.com/ppo/pyhd
  SharpAstrology.HumanDesign   github.com/CReizner/SharpAstrology.HumanDesign
  natalengine                  github.com/Unforced-Dev/natalengine
  hdkit                        github.com/jdempcy/hdkit

Usage: python tools/build_tables.py <dir holding the four clones> <hdkit dir>
"""
import json
import re
import sys
from pathlib import Path

REF = Path(sys.argv[1])
HDKIT = Path(sys.argv[2])
OUT = Path(__file__).resolve().parent.parent / "bodygraph" / "tables.json"

pyhd = (REF / "pyhd/src/pyhd/constants/__init__.py").read_text()
sa = REF / "SharpAstrology.HumanDesign"
ne = (REF / "natalengine/src/calculators/humandesign.js").read_text()
ne_x = (REF / "natalengine/src/data/incarnation-crosses.js").read_text()
hk = (HDKIT / "sample-apps/hdkit_sample_app/app/services/bodygraph_data.rb").read_text()
hk_h = (HDKIT / "sample-apps/hdkit_sample_app/app/helpers/bodygraphs_helper.rb").read_text()

problems = []


def canon_center(s):
    s = s.lower().replace("_", " ").strip()
    return {
        "self": "g", "g center": "g", "g": "g", "mind": "ajna", "ajna": "ajna",
        "crown": "head", "head": "head", "emotions": "solar_plexus",
        "solar": "solar_plexus", "solar plexus": "solar_plexus",
        "heart": "heart", "ego": "heart", "splenic": "spleen", "spleen": "spleen",
        "sacral": "sacral", "root": "root", "throat": "throat",
    }[s]


# ---- gate -> center --------------------------------------------------------
g_sa = {int(a): canon_center(b) for a, b in re.findall(
    r"Gates\.Key(\d+) => Centers\.(\w+)", (sa / "Enums/Gates.cs").read_text())}
g_ne = {int(a): canon_center(b) for a, b in re.findall(
    r"^\s*(\d+): \{ center: '(\w+)'", ne, re.M)}
g_hk = {int(a): canon_center(b) for a, b in re.findall(r'"(\d+)" => \'([\w ]+)\'', hk_h)}
assert len(g_sa) == len(g_ne) == len(g_hk) == 64, (len(g_sa), len(g_ne), len(g_hk))
for g in range(1, 65):
    if not (g_sa[g] == g_ne[g] == g_hk[g]):
        problems.append(f"gate {g} center: SA={g_sa[g]} NE={g_ne[g]} HK={g_hk[g]}")
gate_center = g_sa

gate_names = {int(a): b for a, b in re.findall(
    r"^\s*(\d+): \{ center: '\w+', name: '([^']+)'", ne, re.M)}
iching = {int(a): b for a, b in re.findall(
    r"^\s*(\d+): \{ center: '\w+', name: '[^']+', iching: '([^']+)'", ne, re.M)}

# ---- channels --------------------------------------------------------------
ch_py = {}
for m in re.finditer(
        r'^\s+_(\d\d)_(\d\d)\s+= "([^"]+)",\s+\(Gates\._\d+, Gates\._\d+\),\s+'
        r'ChannelTypes\.(\w+),\s+Circuits\.(\w+),\s+(True|False),\s+CircuitGroups\.(\w+)',
        pyhd, re.M):
    a, b = int(m[1]), int(m[2])
    ch_py[(a, b)] = dict(name=m[3], channel_type=m[4].lower(), circuit=m[5].title(),
                         creative=m[6] == "True", circuit_group=m[7].title())
ch_sa = {tuple(sorted((int(a), int(b)))) for a, b in re.findall(
    r"Channels\.Key\d+Key\d+ => \(Gates\.Key(\d+), Gates\.Key(\d+)\)",
    (sa / "Enums/Channels.cs").read_text())}
ch_ne = {}
for m in re.finditer(r"\{ gates: \[(\d+), (\d+)\], name: '([^']+)', centers: \[[^\]]+\], "
                     r"theme: '[^']*', circuit: '(\w+)', subcircuit: '(\w+)'", ne):
    ch_ne[tuple(sorted((int(m[1]), int(m[2]))))] = dict(name=m[3], group=m[4], circuit=m[5])
ch_hk = {tuple(sorted((int(a), int(b)))) for a, b in re.findall(
    r"\[(\d+), (\d+)\] => \['", hk)}
assert len(ch_py) == 36, len(ch_py)
for label, other in (("SA", ch_sa), ("NE", set(ch_ne)), ("HK", ch_hk)):
    if set(ch_py) != other:
        problems.append(f"channel set differs pyhd vs {label}: {set(ch_py) ^ other}")
NE_CIRC = {"logic": "Understanding", "sensing": "Sensing", "knowing": "Knowing",
           "centering": "Centering", "ego": "Ego", "defense": "Defense",
           "integration": "Integration"}
for k, v in ch_py.items():
    n = ch_ne[k]
    if NE_CIRC[n["circuit"]] != v["circuit"]:
        problems.append(f"channel {k} circuit: pyhd={v['circuit']} NE={n['circuit']}")
    strip = lambda s: re.sub(r"^the ", "", s.lower()).replace("judgement", "judgment")
    if strip(n["name"]) != strip(v["name"]):
        problems.append(f"channel {k} name: pyhd={v['name']!r} NE={n['name']!r}")

# ---- incarnation crosses ---------------------------------------------------
ANG = {"R": "right", "L": "left", "J": "juxtaposition"}
cross = {}
for m in re.finditer(
        r'^\s+_(\d\d)_(\d\d)_(\d\d)_(\d\d)_([RLJ])\s+= "([^"]+)"', pyhd, re.M):
    ps, pe, ds, de = (int(m[i]) for i in range(1, 5))
    # Jovian Archive spells this cross "Endeavour"; two of four sources agree.
    cross[(ps, ANG[m[5]])] = dict(name=m[6].replace("Endeavor", "Endeavour"),
                                  gates=[ps, pe, ds, de])
assert len(cross) == 192, len(cross)


def base(s):
    s = re.sub(r"\s*\d+$", "", s.strip().lower())
    s = re.sub(r"^the ", "", s)
    return re.sub(r"[^a-z]", "", s)


def camel(s):
    return re.sub(r"[^a-z]", "", s.lower())


x_sa = {}
for g, ang, nm in re.findall(
        r"\(Gates\.Key(\d+), Angles\.(\w+)\) => IncarnationCrosses\.(\w+),",
        (sa / "Enums/IncarnationCross.cs").read_text()):
    ang = {"RightAngle": "right", "Right": "right", "LeftAngle": "left", "Left": "left",
           "Juxtaposition": "juxtaposition"}[ang]
    nm = re.sub(r"^(RightAngle|LeftAngle|Juxtaposition)CrossOf(The)?", "", nm)
    x_sa[(int(g), ang)] = re.sub(r"\d+$", "", camel(nm))
x_ne = {}
for g, r, j, l in re.findall(r"^\s*(\d+): \['([^']+)', '([^']+)', '([^']+)'\]", ne_x, re.M):
    x_ne[(int(g), "right")], x_ne[(int(g), "juxtaposition")], x_ne[(int(g), "left")] = (
        base(r), base(j), base(l))
x_hk = {}
for ang, label in (("right", "RIGHT_ANGLE"), ("juxtaposition", "JUXTAPOSITION"),
                   ("left", "LEFT_ANGLE")):
    block = re.search(label + r"_CROSSES_BY_SUN_GATE = \{(.*?)\}", hk, re.S)[1]
    for g, nm in re.findall(r"(\d+) => '([^']+)'", block):
        x_hk[(int(g), ang)] = base(nm)
for label, other in (("SA", x_sa), ("NE", x_ne), ("HK", x_hk)):
    if len(other) != 192:
        problems.append(f"{label} has {len(other)} crosses")
    for k, v in cross.items():
        if k in other and other[k] != base(v["name"]):
            problems.append(f"cross {k}: pyhd={v['name']!r} {label}={other[k]!r}")

# ---- fixations (single source) --------------------------------------------
LN = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5, "Six": 6}
util = (sa / "Utility/HumanDesignUtility.cs").read_text()
fix = {}
table = util[util.index("_getStateFromStatesTable"):util.index("_aggregateStateFromHarmonicGate")]
for block in re.finditer(r"Planets\.(\w+) => \(gate, line\) switch\s*\{(.*?)_ => FixingState\.None",
                         table, re.S):
    planet = {"NorthNode": "north_node", "SouthNode": "south_node"}.get(block[1], block[1].lower())
    for g, l, st in re.findall(r"\(Gates\.Key(\d+), Lines\.(\w+)\) => FixingState\.(\w+)", block[2]):
        fix.setdefault(f"{g}.{LN[l]}", {})[planet] = st.lower()

tables = {
    "gate_center": {str(g): c for g, c in sorted(gate_center.items())},
    "gate_names": {str(g): n for g, n in sorted(gate_names.items())},
    "iching": {str(g): n for g, n in sorted(iching.items())},
    "channels": [
        dict(gates=list(k), centers=[gate_center[k[0]], gate_center[k[1]]], **v)
        for k, v in sorted(ch_py.items())
    ],
    "crosses": {f"{g}:{a}": v for (g, a), v in sorted(cross.items())},
    "fixations": fix,
}
OUT.write_text(json.dumps(tables, indent=1, ensure_ascii=False))
print(f"wrote {OUT}  channels={len(ch_py)} crosses={len(cross)} "
      f"fixation cells={sum(len(v) for v in fix.values())}")
print(f"{len(problems)} disagreements between sources")
for p in problems:
    print("  -", p)
