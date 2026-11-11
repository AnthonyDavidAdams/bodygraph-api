"""HTTP API.

Run:  uvicorn bodygraph.api:app --host 0.0.0.0 --port 8000
Docs: /docs (OpenAPI), /redoc
"""
from __future__ import annotations

import os
from datetime import date as Date
from datetime import datetime, timezone
from functools import lru_cache
from typing import Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from . import __version__, chart as C, data as D, places, render, timeutil
from .ephemeris import EphemerisError, get_engine
from .wheel import GATE_ORDER, gate_span, zodiac

DESCRIPTION = f"""
Free, open Human Design chart calculation and bodygraph rendering.

**Accuracy.** Positions come from Swiss Ephemeris reading JPL-derived data
files, cross-checked against an independent reduction of NASA JPL ephemerides.
The Design moment is solved to the exact 88 degrees of solar arc. The service
reproduces all 104 activations of four published Jovian Archive reference
charts.

**What it does not claim.** {D.DISCLAIMER}
"""

app = FastAPI(title="Bodygraph API", version=__version__, description=DESCRIPTION,
              license_info={"name": "AGPL-3.0-or-later"})
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["GET", "POST"], allow_headers=["*"],
)

MIN_YEAR, MAX_YEAR = 1583, 2999
SVG = "image/svg+xml"
CACHE = "public, max-age=86400"


# --------------------------------------------------------------------------
# input
# --------------------------------------------------------------------------
class Birth(BaseModel):
    """One moment of birth. Give ``utc``, or a local ``date`` and ``time`` with
    one of ``timezone``, ``utc_offset_minutes``, coordinates, or ``place``."""

    utc: Optional[datetime] = Field(None, description="Exact instant, ISO 8601, e.g. 1961-08-05T05:24:00Z")
    date: Optional[Date] = Field(None, description="Local calendar date, YYYY-MM-DD")
    time: Optional[str] = Field(None, description="Local clock time, HH:MM or HH:MM:SS. "
                                                  "Leave out if the time is unknown.")
    timezone: Optional[str] = Field(None, description="IANA zone, e.g. America/New_York")
    utc_offset_minutes: Optional[int] = Field(None, description="Offset in force at birth, e.g. -240")
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    place: Optional[str] = Field(None, description="City to look up, e.g. 'Erie, PA' or 'Montreal, Canada'")
    fold: Optional[Literal[0, 1]] = Field(None, description="For a local time that happened twice "
                                                            "when clocks went back: 0 first, 1 second")
    name: Optional[str] = Field(None, max_length=80)


def birth_query(
    utc: Optional[datetime] = Query(None, description="Exact instant, ISO 8601"),
    date: Optional[Date] = Query(None, description="Local date, YYYY-MM-DD"),
    time: Optional[str] = Query(None, description="Local time, HH:MM or HH:MM:SS"),
    timezone: Optional[str] = Query(None, description="IANA zone"),
    utc_offset_minutes: Optional[int] = Query(None),
    latitude: Optional[float] = Query(None, ge=-90, le=90),
    longitude: Optional[float] = Query(None, ge=-180, le=180),
    place: Optional[str] = Query(None, description="City to look up"),
    fold: Optional[Literal[0, 1]] = Query(None),
    name: Optional[str] = Query(None, max_length=80),
) -> Birth:
    return Birth(utc=utc, date=date, time=time, timezone=timezone,
                 utc_offset_minutes=utc_offset_minutes, latitude=latitude,
                 longitude=longitude, place=place, fold=fold, name=name)


def _parse_time(s: str) -> tuple[int, int, int]:
    try:
        bits = [int(x) for x in s.strip().split(":")]
        if len(bits) == 2:
            bits.append(0)
        h, m, sec = bits
        if not (0 <= h < 24 and 0 <= m < 60 and 0 <= sec < 60):
            raise ValueError
        return h, m, sec
    except ValueError:
        raise HTTPException(422, "time must be HH:MM or HH:MM:SS on a 24 hour clock")


def resolve_birth(b: Birth) -> tuple[timeutil.ResolvedTime, dict]:
    """Return the resolved instant and an echo of how the input was read."""
    info: dict = {}
    warnings: list[dict] = []
    lat, lon, tz = b.latitude, b.longitude, b.timezone
    if b.place and b.utc is None:
        hits = places.search(b.place, 5)
        if not hits:
            raise HTTPException(422, f"No place found for '{b.place}'. Try 'City, Country', "
                                     "or pass a timezone or coordinates.")
        hit = hits[0]
        info["place"] = hit
        if len(hits) > 1:
            warnings.append({"code": "place_ambiguous",
                             "message": "More than one place matched. The largest was used.",
                             "alternatives": hits[1:]})
        tz = tz or hit["timezone"]
        lat, lon = (lat, lon) if lat is not None and lon is not None else (
            hit["latitude"], hit["longitude"])
    local = None
    time_unknown = False
    if b.utc is None:
        if b.date is None:
            raise HTTPException(422, "Give either utc, or date with time and a time zone")
        if b.time is None:
            time_unknown = True
            h, m, s = 12, 0, 0
        else:
            h, m, s = _parse_time(b.time)
        local = datetime(b.date.year, b.date.month, b.date.day, h, m, s)
    try:
        r = timeutil.resolve(local, utc=b.utc, tz=tz,
                             utc_offset_minutes=b.utc_offset_minutes,
                             latitude=lat, longitude=lon, fold=b.fold)
    except timeutil.BirthTimeError as exc:
        raise HTTPException(422, str(exc))
    if not MIN_YEAR <= r.utc.year <= MAX_YEAR:
        raise HTTPException(422, f"Supported years are {MIN_YEAR} to {MAX_YEAR}")
    if time_unknown:
        warnings.append({
            "code": "birth_time_unknown",
            "message": "No birth time was given, so local noon was used. The Moon moves "
                       "about one line every two hours, and type, profile and authority "
                       "can all change within a day. See 'sensitivity' for what holds "
                       "across the whole day.",
        })
    info.update({
        "utc": timeutil.iso_z(r.utc),
        "local": r.local.isoformat() if r.local else None,
        "timezone": r.timezone,
        "utc_offset_minutes": r.utc_offset_minutes,
        "time_source": r.source,
        "time_unknown": time_unknown,
        "name": b.name,
    })
    r.warnings = warnings + r.warnings
    return r, info


@lru_cache(maxsize=4096)
def _chart_cached(utc_iso: str, node: str) -> dict:
    return C.build_chart(datetime.fromisoformat(utc_iso), node=node)


def _chart(utc: datetime, node: str) -> dict:
    try:
        return _chart_cached(utc.astimezone(timezone.utc).isoformat(), node)
    except EphemerisError as exc:
        raise HTTPException(422, str(exc))


def _full(b: Birth, node: str, uncertainty_minutes: Optional[float]) -> dict:
    r, info = resolve_birth(b)
    chart = dict(_chart(r.utc, node))
    margin = C.exact_time_margin(chart)
    warnings = list(r.warnings)
    if margin["minutes"] < 5 and not info["time_unknown"]:
        warnings.append({
            "code": "near_line_boundary",
            "message": f"The {margin['imprint']} {D.BODY_NAMES[margin['body']]} is "
                       f"{margin['minutes']:.1f} minutes of birth time from changing line. "
                       "A birth time rounded to the nearest five minutes could give a "
                       "different chart.",
            **margin,
        })
    window = 720.0 if info["time_unknown"] else uncertainty_minutes
    out = {"input": info, "warnings": warnings, **chart,
           "precision": {"nearest_line_change": margin}}
    if window:
        samples = 289 if window >= 360 else 121
        out["sensitivity"] = C.birth_time_sensitivity(r.utc, window, node=node, samples=samples)
    return out


def _subtitle(info: dict) -> str:
    if info.get("local"):
        dt = datetime.fromisoformat(info["local"])
        when = f"{dt.day} {dt.strftime('%B %Y')}"
        if not info["time_unknown"]:
            when += f", {dt.strftime('%H:%M')}"
        else:
            when += ", time unknown (noon used)"
        place = info.get("place")
        where = f'{place["name"]}, {place["country"]}' if place else (info.get("timezone") or "")
        return ", ".join(x for x in (when, where) if x)
    return "Born " + info["utc"].replace("T", " ").replace("Z", " UTC")


Node = Literal["true", "mean"]
Theme = Literal["light", "dark"]


def _svg(body: str) -> Response:
    return Response(body, media_type=SVG, headers={"Cache-Control": CACHE})


def _png(svg: str, scale: float) -> Response:
    try:
        import cairosvg
    except Exception:  # pragma: no cover
        raise HTTPException(501, "PNG output needs the cairosvg package and libcairo")
    data = cairosvg.svg2png(bytestring=svg.encode(), scale=scale)
    return Response(data, media_type="image/png", headers={"Cache-Control": CACHE})


# --------------------------------------------------------------------------
# natal chart
# --------------------------------------------------------------------------
@app.get("/v1/chart", tags=["chart"], summary="Natal chart as JSON")
def chart_get(b: Birth = Depends(birth_query), node: Node = "true",
              uncertainty_minutes: Optional[float] = Query(
                  None, gt=0, le=720,
                  description="Report what stays the same if the birth time is off by this much")):
    return _full(b, node, uncertainty_minutes)


class ChartRequest(Birth):
    node: Node = "true"
    uncertainty_minutes: Optional[float] = Field(None, gt=0, le=720)


@app.post("/v1/chart", tags=["chart"], summary="Natal chart as JSON")
def chart_post(req: ChartRequest):
    return _full(req, req.node, req.uncertainty_minutes)


def _render_natal(b: Birth, node, theme, layout, center_colors, disclaimer, background) -> str:
    r, info = resolve_birth(b)
    return render.render_svg(_chart(r.utc, node), name=b.name, subtitle=_subtitle(info),
                             theme=theme, layout=layout, center_colors=center_colors,
                             disclaimer=disclaimer, background=background)


@app.get("/v1/chart.svg", tags=["chart"], summary="Bodygraph as SVG",
         response_class=Response, responses={200: {"content": {SVG: {}}}})
def chart_svg(b: Birth = Depends(birth_query), node: Node = "true", theme: Theme = "light",
              layout: Literal["full", "graph"] = "full",
              center_colors: Literal["traditional", "mono"] = "traditional",
              disclaimer: bool = True, background: bool = True):
    return _svg(_render_natal(b, node, theme, layout, center_colors, disclaimer, background))


@app.get("/v1/chart.png", tags=["chart"], summary="Bodygraph as PNG",
         response_class=Response, responses={200: {"content": {"image/png": {}}}})
def chart_png(b: Birth = Depends(birth_query), node: Node = "true", theme: Theme = "light",
              layout: Literal["full", "graph"] = "full",
              center_colors: Literal["traditional", "mono"] = "traditional",
              disclaimer: bool = True, scale: float = Query(2.0, ge=0.5, le=4.0)):
    return _png(_render_natal(b, node, theme, layout, center_colors, disclaimer, True), scale)


# --------------------------------------------------------------------------
# two people
# --------------------------------------------------------------------------
class CompositeRequest(BaseModel):
    a: Birth
    b: Birth
    node: Node = "true"


def _composite(req: CompositeRequest):
    (ra, ia), (rb, ib) = resolve_birth(req.a), resolve_birth(req.b)
    ca, cb = _chart(ra.utc, req.node), _chart(rb.utc, req.node)
    return ca, cb, C.composite(ca, cb), ia, ib, ra.warnings + rb.warnings


@app.post("/v1/composite", tags=["composite"], summary="Connection chart for two people")
def composite_json(req: CompositeRequest):
    ca, cb, comp, ia, ib, warnings = _composite(req)
    brief = lambda c, i: {"input": i, **C.summary_key(c)}
    return {"a": brief(ca, ia), "b": brief(cb, ib), "warnings": warnings, **comp}


@app.post("/v1/composite.svg", tags=["composite"], summary="Connection chart as SVG",
          response_class=Response, responses={200: {"content": {SVG: {}}}})
def composite_svg(req: CompositeRequest, theme: Theme = "light", disclaimer: bool = True):
    ca, cb, comp, ia, ib, _ = _composite(req)
    return _svg(render.render_composite_svg(
        ca, cb, comp, name_a=req.a.name or "Person A", name_b=req.b.name or "Person B",
        theme=theme, disclaimer=disclaimer))


# --------------------------------------------------------------------------
# transits
# --------------------------------------------------------------------------
def _transit_time(at: Optional[datetime]) -> datetime:
    at = at or datetime.now(timezone.utc)
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    if not MIN_YEAR <= at.year <= MAX_YEAR:
        raise HTTPException(422, f"Supported years are {MIN_YEAR} to {MAX_YEAR}")
    return at.replace(microsecond=0)


@app.get("/v1/transit", tags=["transit"], summary="Gate activations of the sky at one moment")
def transit(at: Optional[datetime] = Query(None, description="ISO 8601 instant. Default: now"),
            node: Node = "true"):
    return C.transit_chart(_transit_time(at), node=node)


@app.get("/v1/transit/overlay", tags=["transit"],
         summary="What the sky at one moment completes in a natal chart")
def transit_overlay(b: Birth = Depends(birth_query),
                    at: Optional[datetime] = Query(None), node: Node = "true"):
    r, info = resolve_birth(b)
    natal = _chart(r.utc, node)
    sky = C.transit_chart(_transit_time(at), node=node)
    return {"input": info, "warnings": r.warnings, "transit": sky,
            **C.transit_overlay(natal, sky), "natal": C.summary_key(natal),
            "disclaimer": D.DISCLAIMER}


@app.get("/v1/transit/overlay.svg", tags=["transit"], summary="Transit overlay as SVG",
         response_class=Response, responses={200: {"content": {SVG: {}}}})
def transit_overlay_svg(b: Birth = Depends(birth_query), at: Optional[datetime] = Query(None),
                        node: Node = "true", theme: Theme = "light", disclaimer: bool = True):
    r, _ = resolve_birth(b)
    natal = _chart(r.utc, node)
    sky = C.transit_chart(_transit_time(at), node=node)
    body = render.render_transit_svg(natal, sky, C.transit_overlay(natal, sky), name=b.name,
                                     theme=theme, disclaimer=disclaimer)
    return Response(body, media_type=SVG, headers={"Cache-Control": "no-store"})


# --------------------------------------------------------------------------
# reference and utilities
# --------------------------------------------------------------------------
@app.get("/v1/places", tags=["reference"], summary="Find a city's coordinates and time zone")
def place_search(q: str = Query(..., min_length=2), limit: int = Query(8, ge=1, le=25)):
    return {"query": q, "results": places.search(q, limit)}


@app.get("/v1/reference", tags=["reference"], summary="Gates, channels, centers and the wheel")
def reference():
    gates = []
    for g in GATE_ORDER:
        start, end = gate_span(g)
        gates.append({"gate": g, "name": D.GATE_NAMES[g], "i_ching": D.ICHING[g],
                      "center": D.GATE_CENTER[g], "harmonic_gates": D.HARMONIC[g],
                      "starts_at_longitude": start, "starts_at": zodiac(start)["formatted"],
                      "ends_at": zodiac(end)["formatted"]})
    return {
        "gates_in_wheel_order": gates,
        "channels": D.CHANNELS,
        "centers": [{"key": c, "name": D.CENTER_NAMES[c], "kind": D.CENTER_KIND[c],
                     "gates": D.CENTER_GATES[c]} for c in D.CENTERS],
        "types": D.TYPES, "authorities": D.AUTHORITIES,
        "disclaimer": D.DISCLAIMER,
    }


@app.get("/health", include_in_schema=False)
def health():
    e = get_engine()
    return {"status": "ok", "version": __version__, "engine": e.name, "ephemeris": e.source}


@app.get("/", include_in_schema=False, response_class=HTMLResponse)
def index():
    return f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bodygraph API</title>
<style>body{{font:17px/1.55 system-ui,sans-serif;max-width:44rem;margin:3rem auto;padding:0 1.25rem;color:#12161c}}
code{{background:#f1f3f6;padding:.1em .35em;border-radius:4px}}img{{max-width:100%;border:1px solid #e3e6eb;border-radius:8px}}
.note{{color:#5c6470;border-left:3px solid #d7301f;padding-left:1rem}}</style>
<h1>Bodygraph API</h1>
<p>Free Human Design chart calculation and bodygraph rendering. Version {__version__}.</p>
<p><a href="/docs">Interactive API docs</a></p>
<p>Try it: <code>/v1/chart.svg?date=1961-08-04&amp;time=19:24&amp;place=Honolulu&amp;name=Example</code></p>
<p><img alt="Example bodygraph" src="/v1/chart.svg?date=1961-08-04&amp;time=19:24&amp;place=Honolulu&amp;name=Example"></p>
<p class="note">{D.DISCLAIMER}</p></html>"""
