"""Offline place lookup: city name to coordinates and IANA time zone.

Uses the GeoNames cities set (population over 15,000) through the
``geonamescache`` package, so no geocoding key and no network call.
"""
from __future__ import annotations

import threading
import unicodedata

_LOCK = threading.Lock()
_INDEX = None


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).casefold().strip()


def _load():
    global _INDEX
    with _LOCK:
        if _INDEX is not None:
            return _INDEX
        import geonamescache

        gc = geonamescache.GeonamesCache()
        countries = gc.get_countries()
        states = gc.get_us_states()
        country_names = {_fold(v["name"]): k for k, v in countries.items()}
        country_names.update({"usa": "US", "u.s.": "US", "u.s.a.": "US", "united states of america": "US",
                              "uk": "GB", "england": "GB", "scotland": "GB", "wales": "GB",
                              "britain": "GB", "great britain": "GB", "russia": "RU",
                              "south korea": "KR", "czech republic": "CZ"})
        state_names = {_fold(v["name"]): k for k, v in states.items()}
        by_name: dict[str, list[dict]] = {}
        rows = []
        for c in gc.get_cities().values():
            row = {
                "name": c["name"], "country_code": c["countrycode"],
                "country": countries.get(c["countrycode"], {}).get("name", c["countrycode"]),
                "region": c.get("admin1code") or None,
                "latitude": c["latitude"], "longitude": c["longitude"],
                "timezone": c["timezone"], "population": c["population"],
            }
            rows.append(row)
            keys = {_fold(c["name"])}
            for alt in c.get("alternatenames") or ():
                if alt and alt.isascii():
                    keys.add(_fold(alt))
            for k in keys:
                by_name.setdefault(k, []).append(row)
        _INDEX = (by_name, rows, country_names, state_names)
        return _INDEX


def search(query: str, limit: int = 8) -> list[dict]:
    """Best matches for 'City', 'City, Country' or 'City, State'."""
    by_name, rows, country_names, state_names = _load()
    parts = [p for p in (_fold(x) for x in query.split(",")) if p]
    if not parts:
        return []
    city, quals = parts[0], parts[1:]
    cands = list(by_name.get(city, ()))
    if not cands:
        cands = [r for r in rows if _fold(r["name"]).startswith(city)]

    def keep(r):
        for q in quals:
            cc = country_names.get(q) or (q.upper() if len(q) == 2 else None)
            st = state_names.get(q) or (q.upper() if len(q) == 2 else None)
            ok_country = cc == r["country_code"]
            ok_state = r["country_code"] == "US" and st == r["region"]
            if not (ok_country or ok_state):
                return False
        return True

    seen, out = set(), []
    for r in sorted((r for r in cands if keep(r)), key=lambda r: -r["population"]):
        key = (r["name"], r["country_code"], r["region"])
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out[:limit]
