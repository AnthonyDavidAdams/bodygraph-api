"""Chart construction: two sets of positions in, a full bodygraph out."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from . import data as D
from . import timescale
from .ephemeris import BODIES, Position, get_engine, solve_solar_arc
from .wheel import (GATE_INDEX, LINE_DEG, activation, boundary_distance, gate_span,
                    zodiac)

SCHEMA_VERSION = "1.0"


# --------------------------------------------------------------------------
# time
# --------------------------------------------------------------------------
def _utc_to_tt(engine, utc: datetime) -> float:
    return timescale.utc_to_tt(utc)


def _tt_to_utc(engine, jd_tt: float) -> datetime:
    return timescale.tt_to_utc(jd_tt)


def _iso(dt: datetime) -> str:
    if dt.microsecond >= 500000:
        dt += timedelta(seconds=1)
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + "Z"


# --------------------------------------------------------------------------
# activations
# --------------------------------------------------------------------------
def _activations(positions: dict[str, Position]) -> dict[str, dict]:
    out = {}
    for body in BODIES:
        p = positions[body]
        a = activation(p.longitude)
        back, fwd = boundary_distance(p.longitude, "line")
        speed = abs(p.speed) or 1e-12
        ahead, behind = (fwd, back) if p.speed >= 0 else (back, fwd)
        out[body] = {
            "body": body,
            "gate": a.gate, "line": a.line, "color": a.color, "tone": a.tone, "base": a.base,
            "gate_line": a.gate_line,
            "longitude": round(p.longitude, 7),
            "zodiac": zodiac(p.longitude)["formatted"],
            "speed_deg_per_day": round(p.speed, 7),
            "retrograde": p.retrograde,
            "line_progress": round(back / LINE_DEG if p.speed >= 0 else fwd / LINE_DEG, 4),
            "minutes_since_line_began": round(behind / speed * 1440.0, 1),
            "minutes_until_line_ends": round(ahead / speed * 1440.0, 1),
        }
    return out


def _fixations(own: dict[str, dict], other: dict[str, dict]) -> None:
    """Exaltation and detriment, following SharpAstrology.HumanDesign.

    A line is fixed by a planet named in the line's table entry when that
    planet sits in the same gate or in a harmonic gate, in either imprint.
    """
    for body, act in own.items():
        table = D.FIXATIONS.get(act["gate_line"], {})
        gates = {act["gate"], *D.HARMONIC[act["gate"]]}
        states = {
            table[b2]
            for imprint in (own, other)
            for b2, a2 in imprint.items()
            if a2["gate"] in gates and b2 in table
        }
        act["fixation"] = (
            "juxtaposed" if len(states) == 2 else next(iter(states)) if states else None)


# --------------------------------------------------------------------------
# structure
# --------------------------------------------------------------------------
def _components(channels: list[dict]) -> dict[str, int]:
    """Connected groups of defined centers. Returns center -> group number."""
    parent: dict[str, str] = {}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for ch in channels:
        a, b = ch["centers"]
        parent.setdefault(a, a)
        parent.setdefault(b, b)
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    roots: dict[str, int] = {}
    out = {}
    for c in D.CENTERS:
        if c in parent:
            out[c] = roots.setdefault(find(c), len(roots) + 1)
    return out


def _type(comp: dict[str, int]) -> str:
    if not comp:
        return "Reflector"
    throat = comp.get("throat")
    motor_to_throat = throat is not None and any(comp.get(m) == throat for m in D.MOTORS)
    if "sacral" in comp:
        return "Manifesting Generator" if motor_to_throat else "Generator"
    return "Manifestor" if motor_to_throat else "Projector"


def _authority(comp: dict[str, int], hd_type: str) -> str:
    if "solar_plexus" in comp:
        return "emotional"
    if "sacral" in comp:
        return "sacral"
    if "spleen" in comp:
        return "splenic"
    if "heart" in comp:
        return "ego_manifested" if hd_type == "Manifestor" else "ego_projected"
    if "g" in comp and comp.get("g") == comp.get("throat"):
        return "self_projected"
    return "lunar" if hd_type == "Reflector" else "mental"


def _quarter(gate: int) -> dict:
    idx = GATE_INDEX[gate]
    for start, name, theme in D.QUARTER_START_GATES:
        if (idx - GATE_INDEX[start]) % 64 < 16:
            return {"name": f"Quarter of {name}", "theme": theme}
    raise AssertionError


def _variable(act: dict, vocab: dict | None, label: str) -> dict:
    left = act["tone"] <= 3
    out = {
        "source": label, "color": act["color"], "tone": act["tone"], "base": act["base"],
        "orientation": "left" if left else "right",
    }
    if vocab:
        name, l, r = vocab[act["color"]]
        out["name"] = name
        out["mode"] = l if left else r
    return out


def structure(personality: dict[str, dict], design: dict[str, dict]) -> dict:
    """Everything that follows from the 26 activations."""
    p_gates: dict[int, list[str]] = {}
    d_gates: dict[int, list[str]] = {}
    for body in BODIES:
        p_gates.setdefault(personality[body]["gate"], []).append(body)
        d_gates.setdefault(design[body]["gate"], []).append(body)
    active = set(p_gates) | set(d_gates)

    def side(g: int) -> str:
        return "both" if g in p_gates and g in d_gates else (
            "personality" if g in p_gates else "design")

    channels = []
    for ch in D.CHANNELS:
        a, b = ch["gates"]
        if a in active and b in active:
            sides = {side(a), side(b)}
            channels.append({
                "id": f"{a}-{b}", "gates": [a, b], "name": ch["name"],
                "centers": ch["centers"], "circuit": ch["circuit"],
                "circuit_group": ch["circuit_group"], "channel_type": ch["channel_type"],
                "gate_sides": {str(a): side(a), str(b): side(b)},
                "activation": sides.pop() if len(sides) == 1 else "mixed",
            })
    comp = _components(channels)
    hd_type = _type(comp)
    authority = _authority(comp, hd_type)
    in_channel = {g for ch in channels for g in ch["gates"]}

    centers = {}
    for c in D.CENTERS:
        on = [g for g in D.CENTER_GATES[c] if g in active]
        state = "defined" if c in comp else ("undefined" if on else "open")
        centers[c] = {
            "name": D.CENTER_NAMES[c], "state": state, "defined": c in comp,
            "kind": D.CENTER_KIND[c], "definition_group": comp.get(c),
            "active_gates": on,
            "channels": [ch["id"] for ch in channels if c in ch["centers"]],
        }

    gates = {}
    for g in sorted(active):
        partners = D.HARMONIC[g]
        gates[str(g)] = {
            "gate": g, "name": D.GATE_NAMES[g], "center": D.GATE_CENTER[g],
            "activation": side(g),
            "personality": p_gates.get(g, []), "design": d_gates.get(g, []),
            "in_channel": g in in_channel,
            "hanging": g not in in_channel,
            "harmonic_gates": partners,
        }

    p_sun, d_sun = personality["sun"], design["sun"]
    profile = f"{p_sun['line']}/{d_sun['line']}"
    angle = D.PROFILE_ANGLE.get(profile)
    cross = None
    if angle:
        entry = D.CROSSES[f"{p_sun['gate']}:{angle}"]
        actual = [p_sun["gate"], personality["earth"]["gate"],
                  d_sun["gate"], design["earth"]["gate"]]
        base, _, variant = entry["name"].rpartition(" ")
        if not variant.isdigit():
            base, variant = entry["name"], "1"
        if base.startswith("The "):
            base = "the " + base[4:]
        cross = {
            # Convention: the first variant carries no number.
            "name": f"{D.ANGLE_NAMES[angle]} Cross of {base}"
                    + (f" {variant}" if variant != "1" else ""),
            "variant": int(variant),
            "angle": D.ANGLE_NAMES[angle],
            "gates": {"personality_sun": actual[0], "personality_earth": actual[1],
                      "design_sun": actual[2], "design_earth": actual[3]},
            "notation": f"{actual[0]}/{actual[1]} | {actual[2]}/{actual[3]}",
            "quarter": _quarter(p_sun["gate"]),
            "table_gates_match": entry["gates"] == actual,
        }

    variables = {
        "determination": _variable(d_sun, D.DETERMINATION, "design sun"),
        "environment": _variable(design["north_node"], D.ENVIRONMENT, "design north node"),
        "perspective": _variable(personality["north_node"], D.PERSPECTIVE,
                                 "personality north node"),
        "motivation": _variable(p_sun, D.MOTIVATION, "personality sun"),
    }
    variables["cognition"] = D.COGNITION[d_sun["tone"]]
    arrow = lambda k: "L" if variables[k]["orientation"] == "left" else "R"
    variables["notation"] = (f"P{arrow('motivation')}{arrow('perspective')} "
                             f"D{arrow('determination')}{arrow('environment')}")

    circuits: dict[str, int] = {}
    for ch in channels:
        circuits[ch["circuit"]] = circuits.get(ch["circuit"], 0) + 1

    t = D.TYPES[hd_type]
    return {
        "type": hd_type,
        "strategy": t["strategy"],
        "authority": D.AUTHORITIES[authority],
        "authority_key": authority,
        "signature": t["signature"],
        "not_self_theme": t["not_self"],
        "definition": D.DEFINITIONS[len(set(comp.values()))],
        "definition_groups": [
            [c for c in D.CENTERS if comp.get(c) == n] for n in sorted(set(comp.values()))],
        "profile": {
            "notation": profile,
            "name": f"{D.LINE_NAMES[p_sun['line']]} / {D.LINE_NAMES[d_sun['line']]}",
            "valid": angle is not None,
        },
        "incarnation_cross": cross,
        "centers": centers,
        "defined_centers": [c for c in D.CENTERS if c in comp],
        "undefined_centers": [c for c in D.CENTERS if centers[c]["state"] == "undefined"],
        "open_centers": [c for c in D.CENTERS if centers[c]["state"] == "open"],
        "channels": channels,
        "gates": gates,
        "circuits": circuits,
        "variables": variables,
    }


# --------------------------------------------------------------------------
# public entry points
# --------------------------------------------------------------------------
def build_chart(utc: datetime, *, engine=None, node: str = "true",
                design_arc: float = 88.0) -> dict:
    """A complete natal chart for one UTC instant."""
    if node not in ("true", "mean"):
        raise ValueError("node must be 'true' or 'mean'")
    engine = engine or get_engine()
    jd_p = _utc_to_tt(engine, utc)
    jd_d = solve_solar_arc(engine, jd_p, design_arc)
    pos_p, pos_d = engine.positions(jd_p, node), engine.positions(jd_d, node)
    personality, design = _activations(pos_p), _activations(pos_d)
    _fixations(personality, design)
    _fixations(design, personality)
    design_utc = _tt_to_utc(engine, jd_d)
    arc = (pos_p["sun"].longitude - pos_d["sun"].longitude) % 360.0
    chart = {
        "schema_version": SCHEMA_VERSION,
        "birth": {"utc": _iso(utc.astimezone(timezone.utc)), "julian_day_tt": round(jd_p, 8)},
        "design": {
            "utc": _iso(design_utc), "julian_day_tt": round(jd_d, 8),
            "days_before_birth": round(jd_p - jd_d, 5),
            "solar_arc_degrees": round(arc, 9),
        },
        **structure(personality, design),
        "activations": {"personality": personality, "design": design},
        "calculation": {
            "engine": engine.name, "ephemeris": engine.source,
            "node": node, "design_arc_degrees": design_arc,
            "zodiac": "tropical", "frame": "geocentric apparent, true equinox of date",
            "tt_minus_utc_seconds": round(timescale.tt_minus_utc_seconds(utc), 3),
            "wheel_start": "Gate 41 at 2°00' Aquarius (302°)",
        },
        "disclaimer": D.DISCLAIMER,
    }
    return chart


def summary_key(chart: dict) -> dict:
    """The headline facts used to compare charts across a time window."""
    cross = chart["incarnation_cross"]
    return {
        "type": chart["type"], "authority": chart["authority"],
        "profile": chart["profile"]["notation"], "definition": chart["definition"],
        "incarnation_cross": cross["name"] if cross else None,
        "channels": [c["id"] for c in chart["channels"]],
        "defined_centers": chart["defined_centers"],
        "variables": chart["variables"]["notation"],
    }


def birth_time_sensitivity(utc: datetime, minutes: float, *, engine=None,
                           node: str = "true", samples: int = 121) -> dict:
    """How much of the chart survives an error of +/- ``minutes`` in birth time.

    The window is sampled evenly. Each headline field reports every value it
    takes and the share of the window where it holds.
    """
    engine = engine or get_engine()
    samples = max(3, min(int(samples), 1441))
    step = 2.0 * minutes / (samples - 1)
    seen: dict[str, dict[str, list[float]]] = {}
    line_changes: dict[str, set] = {}
    for i in range(samples):
        off = -minutes + i * step
        c = build_chart(utc + timedelta(minutes=off), engine=engine, node=node)
        for k, v in summary_key(c).items():
            label = ", ".join(v) if isinstance(v, list) else str(v)
            seen.setdefault(k, {}).setdefault(label or "none", []).append(off)
        for imprint in ("personality", "design"):
            for body, a in c["activations"][imprint].items():
                line_changes.setdefault(f"{imprint}.{body}", set()).add(a["gate_line"])
    fields = {}
    for k, vals in seen.items():
        fields[k] = {
            "stable": len(vals) == 1,
            "values": [
                {"value": v, "share": round(len(offs) / samples, 3),
                 "from_minutes": round(min(offs), 2), "to_minutes": round(max(offs), 2)}
                for v, offs in sorted(vals.items(), key=lambda kv: min(kv[1]))
            ],
        }
    moving = {k: sorted(v) for k, v in line_changes.items() if len(v) > 1}
    return {
        "window_minutes": minutes, "samples": samples,
        "stable": all(f["stable"] for f in fields.values()) and not moving,
        "fields": fields,
        "activations_that_change": moving,
    }


def exact_time_margin(chart: dict) -> dict:
    """The shortest time to any gate.line change, from the positions' speeds."""
    best = None
    for imprint in ("personality", "design"):
        for body, a in chart["activations"][imprint].items():
            for direction, key in (("earlier", "minutes_since_line_began"),
                                   ("later", "minutes_until_line_ends")):
                m = a[key]
                if best is None or m < best["minutes"]:
                    best = {"minutes": m, "imprint": imprint, "body": body,
                            "direction": direction, "gate_line": a["gate_line"]}
    return best


def transit_chart(utc: datetime, *, engine=None, node: str = "true") -> dict:
    """Where the 13 bodies stand at one instant, as gate activations."""
    engine = engine or get_engine()
    jd = _utc_to_tt(engine, utc)
    acts = _activations(engine.positions(jd, node))
    gates: dict[int, list[str]] = {}
    for body, a in acts.items():
        gates.setdefault(a["gate"], []).append(body)
    channels = [
        {"id": f"{c['gates'][0]}-{c['gates'][1]}", "name": c["name"], "gates": c["gates"],
         "centers": c["centers"]}
        for c in D.CHANNELS if c["gates"][0] in gates and c["gates"][1] in gates]
    return {
        "utc": _iso(utc.astimezone(timezone.utc)), "activations": acts,
        "gates": {str(g): b for g, b in sorted(gates.items())}, "channels": channels,
        "calculation": {"engine": engine.name, "ephemeris": engine.source, "node": node},
        "disclaimer": D.DISCLAIMER,
    }


def transit_overlay(natal: dict, transit: dict) -> dict:
    """Channels and centers the current sky completes in a natal chart."""
    natal_gates = {int(g) for g in natal["gates"]}
    sky = {int(g) for g in transit["gates"]}
    natal_ch = {c["id"] for c in natal["channels"]}
    completed = []
    for c in D.CHANNELS:
        a, b = c["gates"]
        cid = f"{a}-{b}"
        if cid in natal_ch:
            continue
        have = {a, b} & natal_gates
        missing = {a, b} - have
        if len(have) == 1 and missing <= sky:
            completed.append({"id": cid, "name": c["name"], "centers": c["centers"],
                              "natal_gate": next(iter(have)),
                              "transit_gate": next(iter(missing)),
                              "kind": "completes a hanging gate"})
        elif not have and {a, b} <= sky:
            completed.append({"id": cid, "name": c["name"], "centers": c["centers"],
                              "kind": "whole channel from transit"})
    newly = sorted({c for ch in completed for c in ch["centers"]}
                   - set(natal["defined_centers"]))
    return {"completed_channels": completed, "temporarily_defined_centers": newly}


def composite(a: dict, b: dict) -> dict:
    """Connection chart for two people."""
    ga, gb = {int(g) for g in a["gates"]}, {int(g) for g in b["gates"]}
    out = []
    for c in D.CHANNELS:
        x, y = c["gates"]
        fa, fb = {x, y} <= ga, {x, y} <= gb
        ha, hb = len({x, y} & ga), len({x, y} & gb)
        if fa and fb:
            kind = "companionship"
        elif fa or fb:
            kind = "compromise" if (hb if fa else ha) == 1 else "dominance"
        elif ha == 1 and hb == 1 and ({x, y} & ga) != ({x, y} & gb):
            kind = "electromagnetic"
        else:
            continue
        out.append({"id": f"{x}-{y}", "name": c["name"], "centers": c["centers"],
                    "connection": kind,
                    "a_gates": sorted({x, y} & ga), "b_gates": sorted({x, y} & gb)})
    comp = _components(out)
    counts: dict[str, int] = {}
    for ch in out:
        counts[ch["connection"]] = counts.get(ch["connection"], 0) + 1
    defined = [c for c in D.CENTERS if c in comp]
    return {
        "channels": out, "connection_counts": counts,
        "defined_centers": defined,
        "open_centers": [c for c in D.CENTERS if c not in comp],
        "connection_theme": f"{len(defined)}-{9 - len(defined)}",
        "definition": D.DEFINITIONS[len(set(comp.values()))],
        "disclaimer": D.DISCLAIMER,
    }
