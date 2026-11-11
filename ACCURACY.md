# Accuracy

This file states what the service computes, how each part was checked, and what remains unchecked.

## Method

| Step | Choice | Reason |
|---|---|---|
| Positions | Swiss Ephemeris 2.10.03 reading SE1 data files (JPL DE431) | Sub-arcsecond positions. The file-less Moshier mode is refused. |
| Frame | Geocentric, apparent, tropical, true equinox of date | The convention every Human Design calculator follows. |
| Time | UTC converted to Terrestrial Time with leap seconds | Seconds of birth time are kept. |
| Design moment | Newton solve for the instant the Sun stood exactly 88° earlier | A flat 88 days is wrong by up to several days of solar motion. |
| Lunar node | True (osculating) node. Mean node on request. | Matches Jovian Archive output. |
| Wheel | Gate 41 starts at 2°00' Aquarius (302°) | 64 gates of 5°37'30". |
| Subdivision | Integer arithmetic on 69,120 cells of 18.75" | Line, color, tone and base cannot drift apart. |
| Earth, South Node | Sun + 180°, North Node + 180° | Exact by definition. |

## Evidence

| Check | Result |
|---|---|
| Jovian Archive reference charts (Obama, Biden, Cruise, Winfrey), 104 gate.line activations | 104 of 104, with both engines |
| Type and profile for the same four charts | 4 of 4 |
| Variable arrows for the same four charts, against the natalengine audit | 4 of 4 |
| hdkit's bundled sample chart, 11 Personality positions printed to the arcsecond | 10 within 1", Venus within 3" |
| Ra Uru Hu: 5/1 Manifestor, Splenic, Left Angle Cross of the Clarion, Perspective 6-4 | Match |
| Design solar arc, worst of 2,000 random births | 0.000007" from 88° |
| Design instant, Swiss engine against JPL engine | Worst 0.08 s |
| Incarnation cross gates against the 192-entry table, 400 random births | 400 of 400 |
| All 69,120 wheel cells at start, middle and end | Exact |
| 8 worker threads, 64 concurrent requests | Identical output |

### Two engines that share no astronomy code

`JplEngine` reads NASA JPL DE421 directly and applies light time, solar light deflection, annual aberration, and IAU 2006/2000A precession and nutation through ERFA. It computes the true node from the Moon's state vector. It exists to check the Swiss engine.

Worst disagreement over 2,000 random instants, 1900 to 2049, birth and Design positions together:

| Body | Arcseconds |
|---|---|
| Sun, Earth | 0.005 |
| Mercury, Jupiter, Saturn | 0.007 |
| Mars | 0.03 |
| Moon | 0.05 |
| True node | 0.12 |
| Neptune | 0.17 |
| Uranus, Pluto | 0.28 |
| Venus | 0.34 |

The smallest unit on the wheel, a base, spans 18.75". The two engines gave the same gate and line in every chart and the same Variable arrows in every chart. They differed on a base in 2.7% of charts and on a tone in 0.4%, always where a position sat within a fraction of an arcsecond of an edge. The outer-planet gap reflects the difference between DE421 and DE431.

### What file-less ephemerides cost

hdkit and the SharpAstrology example both run Swiss Ephemeris in Moshier mode. Against the data files, over the same 2,000 births:

| Level | Charts with at least one wrong value |
|---|---|
| Gate or line | 0.5% |
| Color | 4.2% |
| Tone | 22.6% |
| Variable arrow | 7.2% |
| Base | 75.1% |

The true node carries most of the error. Moshier places it up to 50" away from the file-based value.

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
- The C library keeps its data path per thread. A threaded server that sets the path once at start-up serves Moshier results from every other thread, and nothing fails. This service binds the path on each thread and rejects any result that did not come from the data files.

### How tightly the 88° rule is pinned

Barack Obama's Design Moon sits 4.5 minutes of time from the edge between lines 38.4 and 38.5. Jovian prints 38.5. A Design moment more than 4.5 minutes earlier would print 38.4. The published chart therefore confirms the exact solar arc to within about 11" on that side.

## Not verified

- **Color, tone and base against Jovian output.** Jovian's published PDFs print gate and line only. Finer levels rest on the engine agreement above, Ra Uru Hu's documented 6-4 Perspective, and the natalengine audit of four charts.
- **Exaltation and detriment.** The table comes from one source, SharpAstrology.HumanDesign. No second source was available to cross-check it.
- **Gate names and keywords.** One source, natalengine.
- **JPL engine with SPK kernels such as DE440.** The code path exists. Tests ran on DE421 only, because the build sandbox could not reach NASA's servers.
- **The Reddit thread in the brief.** Reddit blocked the fetch.
- **Dates before 1900 and after 2049.** The Swiss engine supports 1583 to 2999. The JPL cross-check covers 1900 to 2049.
- **Time zones before 1970.** The IANA database is incomplete for some regions. The API attaches a warning to every such chart.

## What accuracy means here

The positions are astronomy and can be checked. The meanings Human Design attaches to them cannot. No scientific evidence shows that Human Design describes personality, predicts behavior or outcomes, or helps with decisions. Every response from this service says so.
