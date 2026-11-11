"""Ground truth: four charts published by Jovian Archive (gate.line for all 26
activations each), as transcribed in the natalengine test suite from the
"ZEN Human Design Chart Service" composite PDFs. Birth data are public record.
"""
from datetime import datetime, timezone

import pytest

from bodygraph.chart import build_chart
from bodygraph.ephemeris import JplEngine, SwissEngine

ORDER = ["sun", "earth", "moon", "north_node", "south_node", "mercury", "venus", "mars",
         "jupiter", "saturn", "uranus", "neptune", "pluto"]
CHARTS = [
    ("Obama", (1961, 8, 5, 5, 24), "Projector", "6/2",
     "33.6 19.6 20.4 29.3 30.3 31.1 15.4 47.6 60.5 61.5 29.1 44.2 40.2",
     "2.2 1.2 38.5 59.4 55.4 2.6 21.4 56.4 41.5 60.4 4.3 44.3 59.6", "PRR DLL"),
    ("Biden", (1942, 11, 20, 12, 30), "Generator", "4/6",
     "14.4 8.4 3.5 59.1 55.1 43.3 14.5 44.6 62.5 16.5 20.3 46.4 31.6",
     "29.6 30.6 61.1 59.5 55.5 47.1 31.6 64.3 53.2 35.1 20.5 46.1 31.5", "PRL DLL"),
    ("Cruise", (1962, 7, 3, 19, 6), "Manifestor", "2/5",
     "39.2 38.2 31.1 33.2 19.2 45.4 4.1 8.2 63.2 19.3 29.4 44.4 40.3",
     "21.5 48.5 36.4 7.4 13.4 25.3 3.4 22.1 55.2 19.3 29.3 44.6 40.3", "PRL DRL"),
    ("Winfrey", (1954, 1, 29, 10, 30), "Generator", "2/4",
     "19.2 33.2 34.5 61.4 62.4 49.1 19.2 43.6 35.6 44.2 53.6 32.6 4.6",
     "44.4 24.4 18.4 60.2 56.2 34.1 57.6 46.4 12.4 50.6 62.3 32.4 29.1", "PRL DRR"),
]
ENGINES = {"swisseph": SwissEngine(), "jpl": JplEngine()}


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize("case", CHARTS, ids=[c[0] for c in CHARTS])
def test_all_26_activations(engine, case):
    name, utc, hd_type, profile, p_ref, d_ref, variables = case
    c = build_chart(datetime(*utc, tzinfo=timezone.utc), engine=ENGINES[engine])
    for imprint, ref in (("personality", p_ref), ("design", d_ref)):
        got = [c["activations"][imprint][b]["gate_line"] for b in ORDER]
        assert got == ref.split(), f"{name} {imprint}"
    assert c["type"] == hd_type
    assert c["profile"]["notation"] == profile
    assert c["variables"]["notation"] == variables
    assert c["incarnation_cross"]["table_gates_match"]


def test_ra_uru_hu():
    """Born 9 April 1948, 00:14 EST, Montreal. His Perspective sits on a tone
    edge and reads 6-4 only with file-based ephemerides."""
    c = build_chart(datetime(1948, 4, 9, 5, 14, tzinfo=timezone.utc))
    assert (c["type"], c["profile"]["notation"]) == ("Manifestor", "5/1")
    assert c["authority"] == "Splenic"
    assert c["incarnation_cross"]["name"] == "Left Angle Cross of the Clarion"
    assert c["incarnation_cross"]["notation"] == "51/57 | 61/62"
    p = c["variables"]["perspective"]
    assert (p["color"], p["tone"]) == (6, 4)


def test_hdkit_sample_chart_personality_positions():
    """hdkit ships one chart with positions to the arcsecond (sample-data/
    charts/jonah-dempcy-chart.js): 25 Sep 1983, 20:48 EDT, Malden MA."""
    ref = {"sun": (6, 2, 22, 14), "moon": (1, 15, 39, 58), "north_node": (2, 18, 55, 22),
           "mercury": (5, 16, 29, 40), "venus": (4, 25, 8, 48), "mars": (4, 27, 31, 26),
           "jupiter": (8, 5, 53, 37), "saturn": (7, 3, 7, 19), "uranus": (8, 5, 50, 26),
           "neptune": (8, 26, 32, 53), "pluto": (6, 28, 23, 11)}
    c = build_chart(datetime(1983, 9, 26, 0, 48, tzinfo=timezone.utc))
    for body, (sign, d, m, s) in ref.items():
        want = sign * 30 + d + m / 60 + s / 3600
        got = c["activations"]["personality"][body]["longitude"]
        assert abs(got - want) * 3600 < 3.0, body
