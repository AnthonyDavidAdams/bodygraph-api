# Swiss Ephemeris engine (optional, separate license)

This folder is a separate work under the **GNU AGPL-3.0-or-later**. It is not covered by the Bodygraph API license, and the Bodygraph API does not depend on it.

It wraps Swiss Ephemeris, the library most astrology software uses. Astrodienst AG offers that library under the AGPL or a paid Professional License. The `ephe/*.se1` data files come from https://github.com/aloistr/swisseph. See `ephe/LICENSE-swisseph.txt`.

## Why it is here

It gives the NASA JPL engine a second opinion. The test suite compares the two when `pyswisseph` is installed and skips that comparison when it is absent.

## Before you deploy with it

A public service that runs this engine falls under Swiss Ephemeris licensing. The AGPL does not permit a non-commercial restriction, so it conflicts with the Bodygraph API's own license. Buy the Swiss Ephemeris Professional License first, or keep this engine for private checks.

## Use

```bash
pip install pyswisseph
HD_ENGINE=contrib.swisseph_engine:SwissEngine uvicorn bodygraph.api:app
```
