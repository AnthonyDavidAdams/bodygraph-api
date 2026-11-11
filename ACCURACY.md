# Accuracy

This file states what the service computes, how each part was checked, and what remains unchecked.

## Method

| Step | Choice | Reason |
|---|---|---|
| Planetary data | NASA JPL DE440, read directly | The current NASA ephemeris. Public data with no license condition. |
| Apparent place | Light time, solar light deflection, annual aberration | What an observer at the Earth's center sees. |
| Frame | IAU 2006/2000A precession and nutation (ERFA). Tropical, true equinox of date. | The convention every Human Design calculator follows. |
| Time | UTC to Terrestrial Time. Leap seconds from 1972. Published Delta T splines before that. | Seconds of birth time are kept. |
| Design moment | Newton solve for the instant the Sun stood exactly 88° earlier | A flat 88 days is wrong by up to several days of solar motion. |
| Lunar node | True (osculating) node from the Moon's state vector. Mean node on request. | Matches Jovian Archive output. |
| Wheel | Gate 41 starts at 2°00' Aquarius (302°) | 64 gates of 5°37'30". |
| Subdivision | Integer arithmetic on 69,120 cells of 18.75" | Line, color, tone and base cannot drift apart. |
| Earth, South Node | Sun + 180°, North Node + 180° | Exact by definition. |

## Evidence

| Check | Result |
|---|---|
| Jovian Archive reference charts (Obama, Biden, Cruise, Winfrey), 104 gate.line activations | 104 of 104 with DE440, with DE421, and with Swiss Ephemeris |
| Type and profile for the same four charts | 4 of 4 |
| Variable arrows for the same four charts, against the natalengine audit | 4 of 4 |
| hdkit's bundled sample chart, 11 Personality positions printed to the arcsecond | 10 within 1", Venus within 3" |
| Ra Uru Hu: 5/1 Manifestor, Splenic, Left Angle Cross of the Clarion, Perspective 6-4 | Match |
| Design solar arc, worst of 2,000 random births | 0.000007" from 88° |
| Design instant, NASA engine against Swiss Ephemeris | Worst 0.08 s |
| Incarnation cross gates against the 192-entry table, 400 random births | 400 of 400 |
| All 69,120 wheel cells at start, middle and end | Exact |
| The engine's fast polynomial routine against the jplephem library | Within 2 millimeters |
| 8 worker threads, 64 concurrent requests | Identical output |

### Cross-check against Swiss Ephemeris

Swiss Ephemeris is the library most astrology software uses. It is built on an older NASA file, DE431, and shares no code with this engine. The test suite compares the two whenever `pyswisseph` is installed.

Worst disagreement over 6,000 random instants, 1900 to 2050:

| Body | Arcseconds |
|---|---|
| Sun, Earth | 0.003 |
| Moon | 0.004 |
| Mercury, Venus, Mars | 0.008 |
| Jupiter, Saturn, Uranus, Neptune, Pluto | 0.004 |
| True node | 0.18 |

One exception exists. When a planet sits within 0.3° of the Sun's center, the two engines model the bending of its light differently and disagree by up to 0.8". The planet is behind, in front of, or at the edge of the solar disk at such moments. The table leaves those instants out.

The smallest unit on the wheel, a base, spans 18.75". Across 2,000 full charts the two engines gave the same gate, line, color, tone and Variable arrows every time. They differed on a base in 0.2% of charts, where a position sat within a fraction of an arcsecond of an edge.

Across the rest of the DE440 span, 1583 to 1900 and 2050 to 2598, the planets stay within 0.013", the node within 0.2" and the Moon within 0.3".

### Time scales

From 1972 on, the conversion from UTC to Terrestrial Time is exact and matches Swiss Ephemeris to the millisecond. Before 1972 it uses the Delta T splines of Morrison, Stephenson, Hohenkerk and Zawilski (2021). Those agree with Swiss Ephemeris within 0.7 s back to 1800 and 1.8 s back to 1700. One second moves the Moon half an arcsecond. Before 1700 the Earth's rotation is known to tens of seconds at best, and the two sources differ by up to 20 s.

### What file-less ephemerides cost

hdkit and the SharpAstrology example both run Swiss Ephemeris in Moshier mode, which needs no data files. Against file-based positions, over 2,000 births:

| Level | Charts with at least one wrong value |
|---|---|
| Gate or line | 0.5% |
| Color | 4.2% |
| Tone | 22.6% |
| Variable arrow | 7.2% |
| Base | 75.1% |

The true node carries most of the error. Moshier places it up to 50" away.

### How tightly the 88° rule is pinned

Barack Obama's Design Moon sits 4.5 minutes of time from the edge between lines 38.4 and 38.5. Jovian prints 38.5. A Design moment more than 4.5 minutes earlier would print 38.4. The published chart therefore confirms the exact solar arc to within about 11" on that side.

## Choosing the data file

| `HD_EPHEMERIS` | Years | Notes |
|---|---|---|
| `de440` (default) | 1551 to 2649 | NASA's current file. Installed by the `naif-de440` package. |
| `de421` | 1900 to 2199 | The 2008 file. Small. Agrees with DE440 within 0.03" through Saturn and 0.3" for the outer three. |
| a path to any `.bsp` planetary kernel | set by the file | For example `de440s.bsp` (1849 to 2150, 32 MB) or `de441`. |

`HD_ENGINE=package.module:ClassName` loads a different engine altogether. The optional Swiss Ephemeris add-on in `contrib/` uses this hook.

## Defects found in the reference projects

**hdkit**
- Calculates with `SEFLG_MOSEPH`. See the table above.
- Maps Gate 52 to the Throat in `CENTERS_BY_GATE`. Gate 52 belongs to the Root.
- Detects Manifestors from a fixed list of motor paths. The list omits Heart to Spleen to G to Throat. A chart with channels 26-44, 10-57 and 7-31 comes out as a Projector (traced by reading the code, not by running it). This service searches the graph of defined centers instead.
- Names the Right Angle cross for Sun in Gate 51 "Penetration 2". pyhd and SharpAstrology both give the first variant.
- Falls back to coordinates for Malden, Massachusetts and the New York time zone when no Google key is set, without telling the caller.
- Ships a sample chart whose Design positions do not sit at 88° of solar arc. Its Design Sun is 144" off and its Design Jupiter 21' off. The Personality side of the same file is sound.

**natalengine**
- Files channels 10-34 and 20-57 under the Integration circuit. They belong to Centering and Knowing.
- Its own audit reports a true node within 17" of Swiss and about 4% of charts with a wrong arrow.

**Swiss Ephemeris in a web server**
- The C library keeps its data path per thread. A threaded server that sets the path once at start-up serves Moshier results from every other thread, and nothing fails. The add-on in `contrib/` binds the path on each thread and rejects any result that did not come from the data files.

## Not verified

- **Color, tone and base against Jovian output.** Jovian's published PDFs print gate and line only. Finer levels rest on the agreement with Swiss Ephemeris, Ra Uru Hu's documented 6-4 Perspective, and the natalengine audit of four charts.
- **Exaltation and detriment.** The table comes from one source, SharpAstrology.HumanDesign. No second source was available to cross-check it.
- **Gate names and keywords.** One source, natalengine.
- **Other kernels.** DE440 and DE421 are tested. DE440s and DE441 use the same file format and the same code path, and were not run.
- **The Reddit thread in the brief.** Reddit blocked the fetch.
- **Time zones before 1970.** The IANA database is incomplete for some regions. The API attaches a warning to every such chart.
- **Future dates.** They assume no further leap seconds.

## What accuracy means here

The positions are astronomy and can be checked. The meanings Human Design attaches to them cannot. No scientific evidence shows that Human Design describes personality, predicts behavior or outcomes, or helps with decisions. Every response from this service says so.
