import random
from datetime import datetime, timedelta, timezone

import pytest

from bodygraph.timescale import delta_t_seconds, tt_minus_utc_seconds, tt_to_utc, utc_to_tt

U = timezone.utc


def test_known_offsets_since_1972():
    # 32.184 s plus the leap seconds in force
    for when, want in ((datetime(1972, 1, 1, tzinfo=U), 42.184),
                       (datetime(1980, 6, 1, tzinfo=U), 51.184),
                       (datetime(2000, 1, 1, 12, tzinfo=U), 64.184),
                       (datetime(2016, 12, 31, 23, 59, 59, tzinfo=U), 68.184),
                       (datetime(2017, 1, 1, tzinfo=U), 69.184),
                       (datetime(2026, 11, 10, tzinfo=U), 69.184)):
        assert abs(tt_minus_utc_seconds(when) - want) < 1e-4, when
    assert abs(utc_to_tt(datetime(2000, 1, 1, 12, tzinfo=U)) - 2451545.0 - 64.184 / 86400) < 1e-9


def test_round_trip_and_continuity():
    rng = random.Random(1)
    for _ in range(3000):
        t = datetime(1583, 1, 1, tzinfo=U) + timedelta(seconds=rng.randrange(0, 33_000_000_000))
        assert abs((tt_to_utc(utc_to_tt(t)) - t).total_seconds()) < 2e-3
    before = tt_minus_utc_seconds(datetime(1971, 12, 31, 23, 59, 59, tzinfo=U))
    after = tt_minus_utc_seconds(datetime(1972, 1, 1, tzinfo=U))
    assert abs(after - before) < 0.2      # UT and UTC differed by about this much
    # the spline pieces join without a jump
    for year in (1600, 1700, 1800, 1850, 1900, 1950, 1971):
        assert abs(delta_t_seconds(year - 1e-6) - delta_t_seconds(year + 1e-6)) < 0.01


def test_agrees_with_swiss_ephemeris_time_scales():
    swe = pytest.importorskip("swisseph")
    rng = random.Random(5)
    worst = {}
    for _ in range(6000):
        t = datetime(1700, 1, 1, tzinfo=U) + timedelta(seconds=rng.randrange(0, 10_300_000_000))
        jd_tt, _ = swe.utc_to_jd(t.year, t.month, t.day, t.hour, t.minute, t.second, swe.GREG_CAL)
        era = "1972 on" if t.year >= 1972 else "1800s on" if t.year >= 1800 else "1700s"
        worst[era] = max(worst.get(era, 0.0), abs(utc_to_tt(t) - jd_tt) * 86400)
    assert worst["1972 on"] < 1e-3        # exact
    assert worst["1800s on"] < 1.0        # under a second
    assert worst["1700s"] < 2.5
