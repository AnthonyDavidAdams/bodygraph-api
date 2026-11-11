# Bodygraph API

A free Human Design chart engine and bodygraph renderer. It returns the full chart as JSON and draws it as SVG or PNG.

> **No scientific evidence shows that Human Design describes personality, predicts behavior or outcomes, or helps with decisions.** The planetary positions in a chart are astronomically accurate. The meanings attached to them are not supported by evidence. Every JSON response and every rendered chart carries this notice.

## What it does

- **Natal chart.** Type, strategy, authority, profile, definition, incarnation cross, centers, channels, gates, circuits, all 26 activations to gate, line, color, tone and base, and the four Variables.
- **Bodygraph image.** SVG or PNG, light or dark, full page or graph only. Text ships as outlines, so the chart looks the same in a browser, an email, a PDF or a design tool.
- **Connection chart** for two people, with electromagnetic, compromise, dominance and companionship channels.
- **Transits.** Gate activations for any moment, and what they complete in a natal chart.
- **Birth time checks.** Daylight saving gaps and overlaps, pre-1970 zones, and local mean time all return warnings. Pass `uncertainty_minutes` to see what holds if the time is off. Leave the time out and the API reports what holds across the whole day.
- **Place lookup.** City to coordinates and time zone from bundled GeoNames data. No geocoding key.

## Accuracy

Positions come from Swiss Ephemeris reading its JPL-derived data files. A second engine, written against NASA JPL data with no shared astronomy code, checks the first. The two agree within 0.35 arcseconds on every body. The finest unit on the wheel spans 18.75 arcseconds.

The service reproduces all 104 activations of four reference charts published by Jovian Archive. See [ACCURACY.md](ACCURACY.md) for the method, the evidence, the defects found in other open-source projects, and the list of things not yet verified.

## Run it

```bash
pip install -r requirements.txt
uvicorn bodygraph.api:app --port 8000
```

Open `http://localhost:8000/docs` for interactive documentation.

With Docker:

```bash
docker build -t bodygraph-api .
docker run -p 8000:8000 bodygraph-api
```

On Railway, point a service at this repository. `railway.json` selects the Dockerfile and sets the health check.

## Endpoints

| Method | Path | Returns |
|---|---|---|
| GET, POST | `/v1/chart` | Natal chart, JSON |
| GET | `/v1/chart.svg` | Bodygraph, SVG |
| GET | `/v1/chart.png` | Bodygraph, PNG |
| POST | `/v1/composite` | Connection chart for two people, JSON |
| POST | `/v1/composite.svg` | Connection chart, SVG |
| GET | `/v1/transit` | Gate activations for one moment |
| GET | `/v1/transit/overlay` | Channels the sky completes in a natal chart |
| GET | `/v1/transit/overlay.svg` | The same, drawn |
| GET | `/v1/places?q=` | City search with coordinates and time zone |
| GET | `/v1/reference` | Gates in wheel order, channels, centers |
| GET | `/health` | Engine and data source in use |

### Giving a birth moment

Use one of these. They are tried in this order.

1. `utc=1961-08-05T05:24:00Z`
2. `date` and `time` with `utc_offset_minutes=-600`
3. `date` and `time` with `timezone=Pacific/Honolulu`
4. `date` and `time` with `latitude` and `longitude`
5. `date` and `time` with `place=Honolulu`

```bash
curl "localhost:8000/v1/chart?date=1961-08-04&time=19:24&place=Honolulu"
curl "localhost:8000/v1/chart.svg?date=1961-08-04&time=19:24&place=Honolulu&name=Example" -o chart.svg
curl "localhost:8000/v1/chart.png?utc=1948-04-09T05:14:00Z&theme=dark&scale=2" -o chart.png
```

### Image options

| Parameter | Values | Default |
|---|---|---|
| `theme` | `light`, `dark` | `light` |
| `layout` | `full`, `graph` | `full` |
| `center_colors` | `traditional`, `mono` | `traditional` |
| `background` | `true`, `false` | `true` |
| `disclaimer` | `true`, `false` | `true` |
| `scale` (PNG) | 0.5 to 4 | 2 |

### Calculation options

| Parameter | Values | Default |
|---|---|---|
| `node` | `true`, `mean` | `true` |
| `uncertainty_minutes` | 1 to 720 | off |

## Use as a library

```python
from datetime import datetime, timezone
from bodygraph import build_chart, render_svg

chart = build_chart(datetime(1961, 8, 5, 5, 24, tzinfo=timezone.utc))
print(chart["type"], chart["profile"]["notation"])   # Projector 6/2
open("chart.svg", "w").write(render_svg(chart, name="Example"))
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

## Configuration

| Variable | Meaning | Default |
|---|---|---|
| `HD_ENGINE` | `swisseph` or `jpl` | `swisseph` |
| `SE_EPHE_PATH` | Folder holding the `.se1` files | `./ephe` |
| `JPL_KERNEL` | Path to an SPK kernel such as `de440s.bsp` | bundled DE421 test data |
| `CORS_ORIGINS` | Comma-separated origins | `*` |
| `WEB_CONCURRENCY` | Worker processes | 2 |

## License

AGPL-3.0-or-later. The default engine links Swiss Ephemeris, which Astrodienst offers under the AGPL or a paid Professional License. Running this service in public under the AGPL requires that its source stay available to its users. Callers of the API carry no obligation.

Two routes lead to a different license. Buy the Swiss Ephemeris Professional License, or run with `HD_ENGINE=jpl` and remove `pyswisseph`. The JPL engine depends on MIT and BSD code and public-domain NASA data. It needs a small change first: UTC to TT conversion currently borrows a Swiss Ephemeris routine.

Fonts, data sources and credits are listed in [NOTICE](NOTICE).
