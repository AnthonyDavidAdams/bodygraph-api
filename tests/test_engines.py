"""The two engines share no astronomical code. They must agree."""
import random

import pytest

from bodygraph.ephemeris import JplEngine, SwissEngine, solve_solar_arc
from bodygraph.wheel import CELL_DEG

SW, JP = SwissEngine(), JplEngine()
ARCSEC = 1 / 3600.0
# 1900-01-10 .. 2049-12-01, the span of the bundled DE421 test data
RNG = random.Random(20261110)
DATES = [RNG.uniform(2415030.0, 2469900.0) for _ in range(300)]


def _diff(a, b):
    return abs((a - b + 180.0) % 360.0 - 180.0)


def test_sun_moon_inner_planets_within_a_hundredth_of_an_arcsecond_or_so():
    worst = {}
    for jd in DATES:
        a, b = SW.positions(jd), JP.positions(jd)
        for body in a:
            worst[body] = max(worst.get(body, 0.0), _diff(a[body].longitude, b[body].longitude))
    for body in ("sun", "earth", "moon", "mercury", "venus", "jupiter", "saturn"):
        assert worst[body] < 0.02 * ARCSEC, (body, worst[body] / ARCSEC)
    assert worst["mars"] < 0.05 * ARCSEC
    assert worst["north_node"] < 0.06 * ARCSEC
    # DE421 and DE431 differ slightly for the outer planets
    for body in ("uranus", "neptune", "pluto"):
        assert worst[body] < 0.5 * ARCSEC, (body, worst[body] / ARCSEC)
    # The finest cell on the wheel, a base, is 18.75 arcseconds wide.
    assert max(worst.values()) < CELL_DEG / 40


def test_design_moment_is_exactly_88_degrees():
    for jd in DATES[:120]:
        for eng in (SW, JP):
            jd_d = solve_solar_arc(eng, jd)
            arc = (eng.sun(jd).longitude - eng.sun(jd_d).longitude) % 360.0
            assert abs(arc - 88.0) < 1e-7          # 0.0004 arcseconds
            assert 84.0 < jd - jd_d < 96.0


def test_engines_agree_on_the_design_moment():
    for jd in DATES[:120]:
        dt = abs(solve_solar_arc(SW, jd) - solve_solar_arc(JP, jd)) * 86400.0
        assert dt < 0.2                            # seconds


def test_missing_data_files_fail_loudly(tmp_path):
    from bodygraph.ephemeris import EphemerisError
    with pytest.raises(EphemerisError):
        SwissEngine(ephe_path=str(tmp_path))


def test_worker_threads_use_the_data_files():
    """The C library's state is per thread. Every thread must read the files."""
    from concurrent.futures import ThreadPoolExecutor
    eng = SwissEngine()
    want = eng.positions(2437500.0)["moon"].longitude
    with ThreadPoolExecutor(8) as pool:
        got = list(pool.map(lambda _: eng.positions(2437500.0)["moon"].longitude, range(64)))
    assert all(abs(g - want) < 1e-12 for g in got)
