# Bodygraph API

**by [EarthPilot](https://earthpilot.ai)** · built in the open at the [Singularity Playground](https://earthpilot.ai/playground), a free weekly workshop for people building with AI. Come build with us.

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

Positions come straight from NASA's Jet Propulsion Laboratory. The engine reads the DE440 planetary ephemeris and applies light time, light deflection, aberration, and IAU 2006/2000A precession and nutation.

The service reproduces all 104 activations of four reference charts published by Jovian Archive. It agrees with Swiss Ephemeris, the library most astrology software uses, within 0.01 arcseconds on the Sun, Moon and planets for dates from 1900 to 2050. The finest unit on the wheel spans 18.75 arcseconds.

See [ACCURACY.md](ACCURACY.md) for the method, the evidence, the defects found in other open-source projects, and the list of things not yet verified.

## Run it

```bash
pip install -r requirements.txt
uvicorn bodygraph.api:app --port 8000
```

Open `http://localhost:8000/docs` for interactive documentation. The first install downloads NASA's DE440 file, about 114 MB.

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
| GET | `/health` | Engine, data file and supported years |

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
| `figure` | `true`, `false` | `true` |
| `background` | `true`, `false` | `true` |
| `disclaimer` | `true`, `false` | `true` |
| `scale` (PNG) | 0.5 to 4 | 2 |

### Calculation options

| Parameter | Values | Default |
|---|---|---|
| `node` | `true`, `mean` | `true` |
| `uncertainty_minutes` | 1 to 720 | off |

## Choosing the data

The engine reads any NASA JPL planetary file. Set `HD_EPHEMERIS`.

| Value | Years | Size | Notes |
|---|---|---|---|
| `de440` (default) | 1551 to 2649 | 114 MB | NASA's current file. Installed with the requirements. |
| `de421` | 1900 to 2199 | 27 MB | The 2008 file. `pip install de421`. |
| `/path/to/file.bsp` | set by the file | varies | Any SPK planetary kernel, such as `de440s.bsp` or `de441.bsp` from [NAIF](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/). |

A different engine can replace the built-in one. Set `HD_ENGINE=package.module:ClassName`. The class needs `name`, `source`, `sun(jd_tt)` and `positions(jd_tt, node)`.

`contrib/swisseph_engine` holds one such engine, a Swiss Ephemeris adapter. It is a separate work under the AGPL and the Docker image leaves it out. Read its README before you deploy with it.

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

The Swiss Ephemeris cross-check runs when `pyswisseph` is installed and is skipped otherwise.

## Configuration

| Variable | Meaning | Default |
|---|---|---|
| `HD_EPHEMERIS` | `de440`, `de421`, or a path to a `.bsp` file | `de440` |
| `HD_ENGINE` | `jpl`, or `package.module:ClassName` | `jpl` |
| `CORS_ORIGINS` | Comma-separated origins | `*` |
| `WEB_CONCURRENCY` | Worker processes | 2 |

## Install as a package

```bash
pip install "git+https://github.com/AnthonyDavidAdams/bodygraph-api"          # library only
pip install "bodygraph[api] @ git+https://github.com/AnthonyDavidAdams/bodygraph-api"  # plus the web service
```

It draws the bodygraphs on [Personality Bench](https://persona.earthpilot.ai), where every AI model gets a chart from its release date as a novelty.

## About

Built by Anthony David Adams at the EarthPilot.ai Lab. If you build with AI, join us at the [Singularity Playground](https://earthpilot.ai/playground).

## License

[MIT](LICENSE). Use it for anything, commercial work included. Keep the copyright notice.

The planetary data is a NASA work with no license condition. Every runtime dependency carries a permissive license. See [NOTICE](NOTICE) for credits and [CONTRIBUTING.md](CONTRIBUTING.md) for how to contribute. The optional Swiss Ephemeris add-on in `contrib/` is not covered: it is AGPL.
