"""The NASA JPL engine, its data options, and the Swiss Ephemeris cross-check.

The two engines share no astronomical code. They must agree.
"""
import random
from concurrent.futures import ThreadPoolExecutor

import pytest

from bodygraph import ephemeris
from bodygraph.ephemeris import EphemerisError, JplEngine, solve_solar_arc
from bodygraph.wheel import CELL_DEG

ARCSEC = 1 / 3600.0
RNG = random.Random(20261110)
DATES = [RNG.uniform(2415030.0, 2469900.0) for _ in range(300)]       # 1900 to 2050
OLD = [RNG.uniform(2299200.0, 2415000.0) for _ in range(150)]         # 1583 to 1900
FAR = [RNG.uniform(2470000.0, 2670000.0) for _ in range(150)]         # 2050 to 2598


def _diff(a, b):
    return abs((a - b + 180.0) % 360.0 - 180.0)


def _worst(e1, e2, dates):
    worst = {}
    for jd in dates:
        a, b = e1.positions(jd), e2.positions(jd)
        for body in a:
            worst[body] = max(worst.get(body, 0.0), _diff(a[body].longitude, b[body].longitude))
    return worst


def test_de440_matches_swiss_ephemeris_1900_to_2050(de440, swiss):
    worst = _worst(de440, swiss, DATES)
    for body, d in worst.items():
        limit = 0.25 if body.endswith("node") else 0.02
        assert d < limit * ARCSEC, (body, d / ARCSEC)
    # The finest cell on the wheel, a base, is 18.75 arcseconds wide.
    assert max(worst.values()) < CELL_DEG / 150


def test_de440_matches_swiss_ephemeris_across_its_whole_span(de440, swiss):
    for dates in (OLD, FAR):
        worst = _worst(de440, swiss, dates)
        for body, d in worst.items():
            # the Moon's long-term motion differs slightly between DE431 and DE440
            limit = 0.5 if body in ("moon", "north_node", "south_node") else 0.05
            assert d < limit * ARCSEC, (body, d / ARCSEC)


def test_de421_and_de440_agree(de421, de440):
    worst = _worst(de421, de440, DATES)
    assert max(worst.values()) < 0.5 * ARCSEC


def test_speeds_match_swiss(de440, swiss):
    for jd in DATES[:60]:
        a, b = de440.positions(jd), swiss.positions(jd)
        for body in a:
            assert abs(a[body].speed - b[body].speed) < 0.01, body
            assert a[body].retrograde == b[body].retrograde or abs(b[body].speed) < 0.005


def test_design_moment_is_exactly_88_degrees(de440):
    for jd in DATES[:150]:
        jd_d = solve_solar_arc(de440, jd)
        arc = (de440.sun(jd).longitude - de440.sun(jd_d).longitude) % 360.0
        assert abs(arc - 88.0) < 1e-7              # 0.0004 arcseconds
        assert 84.0 < jd - jd_d < 96.0


def test_engines_agree_on_the_design_moment(de440, swiss):
    for jd in DATES[:150]:
        dt = abs(solve_solar_arc(de440, jd) - solve_solar_arc(swiss, jd)) * 86400.0
        assert dt < 0.2                            # seconds


def test_fast_evaluator_matches_jplephem(de440):
    """The plain-float Chebyshev routine against the library's own."""
    import numpy as np
    for jd in DATES[:40] + OLD[:20] + FAR[:20]:
        for pair, seg in de440._seg.items():
            p, v = de440._kernel[pair].compute_and_differentiate(jd)
            mp, mv = seg.pv(jd)
            assert np.max(np.abs(np.array(mp) * seg.au - p)) < 1e-4       # km
            assert np.max(np.abs(np.array(mv) * seg.au - v)) < 1e-4       # km per day


def test_worker_threads_get_identical_answers(de440):
    want = de440.positions(2437500.0)
    with ThreadPoolExecutor(8) as pool:
        got = list(pool.map(lambda i: de440.positions(2437500.0 + (i % 2) * 5000.0), range(64)))
    for i, g in enumerate(got):
        if i % 2 == 0:
            assert g == want


def test_dataset_options(tmp_path, de440, de421):
    assert de440.year_range() == (1551, 2649)
    assert de421.year_range()[0] <= 1900 and de421.year_range()[1] >= 2050
    import naif_de440
    by_path = JplEngine(naif_de440.de440)                 # any SPK file by path
    assert by_path.positions(2451545.0) == de440.positions(2451545.0)
    with pytest.raises(EphemerisError, match="not found"):
        JplEngine(str(tmp_path / "missing.bsp"))
    with pytest.raises(EphemerisError, match="covers the years 1551 to 2649"):
        de440.positions(2200000.0)


def test_engine_plugin_hook(monkeypatch):
    pytest.importorskip("swisseph")
    monkeypatch.setattr(ephemeris, "_ENGINE", None)
    monkeypatch.setenv("HD_ENGINE", "contrib.swisseph_engine:SwissEngine")
    assert ephemeris.get_engine().name == "swisseph"
    monkeypatch.setattr(ephemeris, "_ENGINE", None)
    monkeypatch.setenv("HD_ENGINE", "no.such.module:Thing")
    with pytest.raises(EphemerisError):
        ephemeris.get_engine()
    monkeypatch.setattr(ephemeris, "_ENGINE", None)


def test_swiss_addon_refuses_to_run_without_its_data_files(tmp_path):
    pytest.importorskip("swisseph")
    from contrib.swisseph_engine import SwissEngine, SwissEphemerisError
    with pytest.raises(SwissEphemerisError):
        SwissEngine(ephe_path=str(tmp_path))
