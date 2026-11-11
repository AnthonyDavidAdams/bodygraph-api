from datetime import datetime

from fastapi.testclient import TestClient

from bodygraph import timeutil
from bodygraph.api import app

client = TestClient(app)


def test_historical_offsets():
    r = timeutil.resolve(datetime(1942, 11, 20, 8, 30), tz="America/New_York")
    assert r.utc_offset_minutes == -240                     # US War Time
    r = timeutil.resolve(datetime(1961, 8, 4, 19, 24), tz="Pacific/Honolulu")
    assert r.utc.isoformat() == "1961-08-05T05:24:00+00:00"


def test_ambiguous_and_nonexistent_times_are_reported():
    r = timeutil.resolve(datetime(2021, 11, 7, 1, 30), tz="America/New_York")
    assert r.warnings[0]["code"] == "ambiguous_local_time"
    assert len(r.warnings[0]["candidates_utc"]) == 2
    later = timeutil.resolve(datetime(2021, 11, 7, 1, 30), tz="America/New_York", fold=1)
    assert (later.utc - r.utc).total_seconds() == 3600 and not later.warnings
    r = timeutil.resolve(datetime(2021, 3, 14, 2, 30), tz="America/New_York")
    assert r.warnings[0]["code"] == "nonexistent_local_time"
    r = timeutil.resolve(datetime(1850, 6, 1, 12, 0), tz="Europe/Paris")
    assert r.warnings[0]["code"] == "local_mean_time"


def test_chart_by_place():
    r = client.get("/v1/chart", params={"date": "1961-08-04", "time": "19:24",
                                        "place": "Honolulu", "name": "Example"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["input"]["utc"] == "1961-08-05T05:24:00Z"
    assert j["input"]["timezone"] == "Pacific/Honolulu"
    assert (j["type"], j["profile"]["notation"]) == ("Projector", "6/2")
    assert "No scientific evidence" in j["disclaimer"]
    # The Design Moon is under five minutes from a line edge in this chart.
    assert any(w["code"] == "near_line_boundary" for w in j["warnings"])


def test_three_ways_to_give_the_same_moment_agree():
    a = client.get("/v1/chart", params={"utc": "1954-01-29T10:30:00Z"}).json()
    b = client.get("/v1/chart", params={"date": "1954-01-29", "time": "04:30",
                                        "utc_offset_minutes": -360}).json()
    c = client.post("/v1/chart", json={"date": "1954-01-29", "time": "04:30:00",
                                       "latitude": 33.0576, "longitude": -89.5876}).json()
    assert a["activations"] == b["activations"] == c["activations"]
    assert c["input"]["timezone"] == "America/Chicago"


def test_unknown_time_returns_a_day_wide_sensitivity_report():
    j = client.get("/v1/chart", params={"date": "1990-06-15", "timezone": "Europe/London"}).json()
    assert j["input"]["time_unknown"]
    assert j["warnings"][0]["code"] == "birth_time_unknown"
    s = j["sensitivity"]
    assert s["window_minutes"] == 720 and "personality.moon" in s["activations_that_change"]
    for f in s["fields"].values():
        assert abs(sum(v["share"] for v in f["values"]) - 1.0) < 0.02


def test_bad_input_is_a_422_with_a_reason():
    assert client.get("/v1/chart").status_code == 422
    assert client.get("/v1/chart", params={"date": "1990-01-01", "time": "25:00",
                                           "timezone": "UTC"}).status_code == 422
    assert client.get("/v1/chart", params={"date": "1990-01-01", "time": "10:00"}).status_code == 422
    assert client.get("/v1/chart", params={"date": "1990-01-01", "time": "10:00",
                                           "timezone": "Mars/Olympus"}).status_code == 422
    assert client.get("/v1/chart", params={"utc": "1200-01-01T00:00:00Z"}).status_code == 422


def test_svg_and_png():
    q = {"utc": "1948-04-09T05:14:00Z", "name": "R & <b>"}
    for theme in ("light", "dark"):
        for layout in ("full", "graph"):
            r = client.get("/v1/chart.svg", params={**q, "theme": theme, "layout": layout})
            assert r.status_code == 200 and r.headers["content-type"].startswith("image/svg")
            body = r.text
            assert body.startswith("<svg") and "<b>" not in body and "<text" not in body
            assert "No scientific evidence" in body
            import xml.dom.minidom
            xml.dom.minidom.parseString(body)
    r = client.get("/v1/chart.png", params={**q, "scale": 1})
    assert r.status_code == 200 and r.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_composite_transit_places_reference():
    body = {"a": {"utc": "1954-01-29T10:30:00Z", "name": "A"},
            "b": {"utc": "1948-04-09T05:14:00Z", "name": "B"}}
    j = client.post("/v1/composite", json=body).json()
    assert j["connection_theme"] == "9-0" and j["a"]["type"] == "Generator"
    assert client.post("/v1/composite.svg", json=body).text.startswith("<svg")
    t = client.get("/v1/transit", params={"at": "2026-11-11T01:40:00Z"}).json()
    assert len(t["activations"]) == 13
    o = client.get("/v1/transit/overlay", params={"utc": "1954-01-29T10:30:00Z",
                                                  "at": "2026-11-11T01:40:00Z"}).json()
    assert "completed_channels" in o
    assert client.get("/v1/transit/overlay.svg", params={
        "utc": "1954-01-29T10:30:00Z"}).text.startswith("<svg")
    p = client.get("/v1/places", params={"q": "Erie, PA"}).json()["results"][0]
    assert p["timezone"] == "America/New_York" and p["country_code"] == "US"
    ref = client.get("/v1/reference").json()
    assert len(ref["gates_in_wheel_order"]) == 64 and len(ref["channels"]) == 36
    h = client.get("/health").json()
    assert h["status"] == "ok" and h["engine"] == "jpl" and "DE440" in h["ephemeris"]
    assert h["years"] == [1583, 2649]
    assert client.get("/v1/transit", params={"at": "2700-01-01T00:00:00Z"}).status_code == 422
    old = client.get("/v1/chart", params={"utc": "1650-03-01T12:00:00Z"})
    assert old.status_code == 200 and old.json()["calculation"]["tt_minus_utc_seconds"] > 30
    assert client.get("/").status_code == 200


def test_rendering_is_thread_safe():
    """Fresh process state, many threads, text never shaped before."""
    import subprocess, sys
    code = (
        "from concurrent.futures import ThreadPoolExecutor\n"
        "from datetime import datetime, timezone, timedelta\n"
        "from bodygraph import build_chart, render_svg\n"
        "t0 = datetime(1970, 1, 1, tzinfo=timezone.utc)\n"
        "def one(i):\n"
        "    c = build_chart(t0 + timedelta(days=97 * i, minutes=13 * i))\n"
        "    return render_svg(c, name=f'Person {i} Qwerty Zxcv')[:4]\n"
        "with ThreadPoolExecutor(16) as pool:\n"
        "    assert set(pool.map(one, range(96))) == {'<svg'}\n"
    )
    for _ in range(3):
        subprocess.run([sys.executable, "-c", code], check=True)
