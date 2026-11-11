"""Static Human Design vocabulary and the cross-checked lookup tables."""
from __future__ import annotations

import json
from pathlib import Path

_T = json.loads((Path(__file__).parent / "tables.json").read_text())

GATE_CENTER: dict[int, str] = {int(k): v for k, v in _T["gate_center"].items()}
GATE_NAMES: dict[int, str] = {int(k): v for k, v in _T["gate_names"].items()}
ICHING: dict[int, str] = {int(k): v for k, v in _T["iching"].items()}
CHANNELS: list[dict] = _T["channels"]
CROSSES: dict[str, dict] = _T["crosses"]
FIXATIONS: dict[str, dict[str, str]] = _T["fixations"]

CENTERS = ("head", "ajna", "throat", "g", "heart", "spleen", "solar_plexus", "sacral", "root")
CENTER_NAMES = {
    "head": "Head", "ajna": "Ajna", "throat": "Throat", "g": "G", "heart": "Heart",
    "spleen": "Spleen", "solar_plexus": "Solar Plexus", "sacral": "Sacral", "root": "Root",
}
CENTER_KIND = {
    "head": "pressure", "ajna": "awareness", "throat": "manifestation", "g": "identity",
    "heart": "motor", "spleen": "awareness", "solar_plexus": "motor and awareness",
    "sacral": "motor", "root": "motor and pressure",
}
MOTORS = ("heart", "solar_plexus", "sacral", "root")
CENTER_GATES: dict[str, list[int]] = {
    c: sorted(g for g, cc in GATE_CENTER.items() if cc == c) for c in CENTERS
}
HARMONIC: dict[int, list[int]] = {g: [] for g in range(1, 65)}
for _c in CHANNELS:
    _a, _b = _c["gates"]
    HARMONIC[_a].append(_b)
    HARMONIC[_b].append(_a)

TYPES = {
    "Generator": dict(strategy="Wait to respond", signature="Satisfaction",
                      not_self="Frustration", aura="Open and enveloping"),
    "Manifesting Generator": dict(strategy="Wait to respond, then inform",
                                  signature="Satisfaction", not_self="Frustration and anger",
                                  aura="Open and enveloping"),
    "Manifestor": dict(strategy="Inform before acting", signature="Peace",
                       not_self="Anger", aura="Closed and repelling"),
    "Projector": dict(strategy="Wait for the invitation", signature="Success",
                      not_self="Bitterness", aura="Focused and absorbing"),
    "Reflector": dict(strategy="Wait a lunar cycle", signature="Surprise",
                      not_self="Disappointment", aura="Resistant and sampling"),
}

AUTHORITIES = {
    "emotional": "Emotional (Solar Plexus)",
    "sacral": "Sacral",
    "splenic": "Splenic",
    "ego_manifested": "Ego Manifested",
    "ego_projected": "Ego Projected",
    "self_projected": "Self-Projected",
    "mental": "Mental (Environment)",
    "lunar": "Lunar",
}

DEFINITIONS = {0: "No Definition", 1: "Single Definition", 2: "Split Definition",
               3: "Triple Split Definition", 4: "Quadruple Split Definition"}

LINE_NAMES = {1: "Investigator", 2: "Hermit", 3: "Martyr", 4: "Opportunist",
              5: "Heretic", 6: "Role Model"}
PROFILE_ANGLE = {
    "1/3": "right", "1/4": "right", "2/4": "right", "2/5": "right", "3/5": "right",
    "3/6": "right", "4/6": "right", "4/1": "juxtaposition",
    "5/1": "left", "5/2": "left", "6/2": "left", "6/3": "left",
}
ANGLE_NAMES = {"right": "Right Angle", "left": "Left Angle", "juxtaposition": "Juxtaposition"}

# The four Quarters open at gates 13, 2, 7 and 1 on the wheel.
QUARTER_START_GATES = ((13, "Initiation", "Mind"), (2, "Civilization", "Form"),
                       (7, "Duality", "Bonding"), (1, "Mutation", "Transformation"))

# Variable vocabulary, indexed by color 1..6. Each entry is (name, left, right).
DETERMINATION = {1: ("Appetite", "Consecutive", "Alternating"), 2: ("Taste", "Open", "Closed"),
                 3: ("Thirst", "Hot", "Cold"), 4: ("Touch", "Calm", "Nervous"),
                 5: ("Sound", "High", "Low"), 6: ("Light", "Direct", "Indirect")}
ENVIRONMENT = {1: ("Caves", "Selective", "Blending"), 2: ("Markets", "Internal", "External"),
               3: ("Kitchens", "Wet", "Dry"), 4: ("Mountains", "Active", "Passive"),
               5: ("Valleys", "Narrow", "Wide"), 6: ("Shores", "Natural", "Artificial")}
PERSPECTIVE = {1: ("Survival", "Focused", "Peripheral"), 2: ("Possibility", "Focused", "Peripheral"),
               3: ("Power", "Focused", "Peripheral"), 4: ("Wanting", "Focused", "Peripheral"),
               5: ("Probability", "Focused", "Peripheral"), 6: ("Personal", "Focused", "Peripheral")}
MOTIVATION = {1: ("Fear", "Strategic", "Receptive"), 2: ("Hope", "Strategic", "Receptive"),
              3: ("Desire", "Strategic", "Receptive"), 4: ("Need", "Strategic", "Receptive"),
              5: ("Guilt", "Strategic", "Receptive"), 6: ("Innocence", "Strategic", "Receptive")}
COGNITION = {1: "Smell", 2: "Taste", 3: "Outer Vision", 4: "Inner Vision", 5: "Feeling", 6: "Touch"}

BODY_NAMES = {
    "sun": "Sun", "earth": "Earth", "north_node": "North Node", "south_node": "South Node",
    "moon": "Moon", "mercury": "Mercury", "venus": "Venus", "mars": "Mars",
    "jupiter": "Jupiter", "saturn": "Saturn", "uranus": "Uranus", "neptune": "Neptune",
    "pluto": "Pluto",
}
BODY_GLYPHS = {
    "sun": "☉", "earth": "⊕", "north_node": "☊", "south_node": "☋",
    "moon": "☽", "mercury": "☿", "venus": "♀", "mars": "♂",
    "jupiter": "♃", "saturn": "♄", "uranus": "♅", "neptune": "♆",
    "pluto": "♇",
}

DISCLAIMER = (
    "Human Design is a belief system created in 1987. No scientific evidence "
    "shows that it describes personality, predicts behavior or outcomes, or is "
    "useful for making decisions. The planetary positions in this chart are "
    "astronomically accurate. The meanings attached to them are not supported "
    "by evidence. Do not use this chart for medical, psychological, financial, "
    "hiring or legal decisions."
)
DISCLAIMER_SHORT = (
    "No scientific evidence shows Human Design is useful or predictive. "
    "Positions are astronomically accurate. The meanings are not evidence-based."
)
