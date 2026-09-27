# aime-data

Pre-built landmark cells for **Aimé**, the Construct module that turns a tap in a
photo into a compass bearing and ranks the named landmarks along it
(`blueworkslabs/construct`, `docs/aime-brief.md`). This repository holds the
monthly build pipeline; the built files are published on Cloudflare Pages.

Coverage: **Germany and Austria** (every 1° cell that intersects either
country). Source: Overture Maps, one release per build. Licence of the
published data: **ODbL 1.0** (see `DATA-LICENSE.md`).

Evidence for this design: `experiments/aime-overture-spike/README.md` in
`blueworkslabs/construct` (spike of 2026-09-27, draft PR #36).

## Data contract, schema 1

This contract is what the Aimé module relies on. Changing field meaning or
layout requires `schema: 2` and a module update.

### Layout

```
public/
  _headers
  index.html        (attribution and licence page)
  v1/
    index.json
    <dataset>/cells/<lat>_<lon>.json
```

- `<dataset>` is `<release>-r<revision>`: the Overture release, e.g.
  `2026-09-23.1`, plus a data revision starting at 1. A rule fix or correction
  that changes any byte for the same Overture release becomes the next
  revision (`-r2`, …). A published dataset path never changes; `force` does not
  override that, and an identical rebuild publishes nothing.
- A cell covers `lat ≤ φ < lat+1`, `lon ≤ λ < lon+1`; names use the integer
  south-west corner, e.g. `50_8.json`, `47_-1.json`, `-34_18.json`.
- Only non-empty cells are written; `index.json` lists them.
- The current and the previous dataset are kept; older ones are removed. An
  older Overture release is never published over a newer one.

### `v1/index.json`

```json
{
  "schema": 1,
  "release": "2026-09-23.1",
  "revision": 1,
  "dataset": "2026-09-23.1-r1",
  "built": "2026-09-27T12:00:00Z",
  "cellDeg": 1,
  "coverage": ["DE", "AT"],
  "path": "2026-09-23.1-r1/cells/",
  "cells": ["46_9", "46_10", "47_5"],
  "license": "ODbL-1.0",
  "attribution": "© OpenStreetMap contributors, Overture Maps Foundation",
  "kinds": ["bell_tower", "bridge", "castle", "…"]
}
```

`kinds` is the list of every kind that can appear, for validation and labels
only. It carries no position values: position uncertainty is per feature.

### `v1/<dataset>/cells/<lat>_<lon>.json`

```json
{
  "schema": 1,
  "release": "2026-09-23.1",
  "revision": 1,
  "cell": [50, 8],
  "declination": 3.8,
  "f": [["Großer Feldberg", "peak", 50.23237, 8.45694, 879, 1.8, 8]]
}
```

A cell whose `release` or `revision` differs from the index is unavailable.
`declination` (additive, 2026-09-27) is the magnetic declination at the cell
centre in degrees east of true north, one decimal: WMM2025 at sea level, with
the Overture release date as the epoch so identical rebuilds stay identical.
The Aimé module takes it from the viewpoint's cell to turn the phone's magnetic
compass hint into a true bearing, and skips the heading when it is absent;
clients must accept cells without it and ignore it when they don't use it.
Each feature is `[name, kind, lat, lon, e, w, p]`:

| Field | Meaning |
| --- | --- |
| `name` | Primary name, NFC, at most 80 characters, never empty |
| `kind` | One of `index.kinds` (list below) |
| `lat`, `lon` | WGS84 degrees, 5 decimals: the centre of the Overture bounding box |
| `e` | Elevation above sea level in metres for peak/hill/volcano; structure height in metres for everything else; `0` when unknown |
| `w` | Visibility weight, 0.5–2.0, one decimal (see below) |
| `p` | Position uncertainty in metres, integer 5–1000 (see below). The module uses it directly as the landmark's 1σ position uncertainty (`positionM`) for marks and candidates |

A cell file must stay under **1 MiB** of JSON; the build fails otherwise (the
host caps JSON responses at 2 MiB). Features are sorted by `w` descending,
then name, for stable diffs.

### Kinds

Terrain: `peak`, `hill`, `volcano`. Structures: `tower`, `observation`,
`communication_tower`, `mast`, `bell_tower`, `water_tower`, `watchtower`,
`minaret`, `lighthouse`, `windmill`, `chimney`, `radar`. Buildings: `church`,
`cathedral`, `chapel`, `mosque`, `synagogue`, `temple`, `monastery`, `castle`,
`ruins`, `fort`, `tall_building`, `gasometer`, `cooling`. Others: `monument`,
`memorial`, `bridge`, `dam`. A kind says what a landmark is, not how precisely
it is placed.

### Position uncertainty `p`

`p = clamp(max(floor(source), 0.5 × half-diagonal), 5, 1000)` metres, rounded
up. The half-diagonal is half the diagonal of the Overture bounding box
(0 for points). The tapped part of a landmark lies inside its bbox, so the
half-diagonal is a hard bound, and for a point spread over a box the
cross-track RMS is about 0.3–0.4 of it: 0.5 × half-diagonal is a conservative
1σ. Floors by the source of the kept record:

| Source | Floor |
| --- | --- |
| `land`, `infra` (OSM via Overture base) | 8 m |
| `buildings` (footprints) | 10 m |
| `places` (geocoded POIs: castle, fort, monument, lighthouse, memorial, historic site, church fallback) | 60 m |
| `places` mountain fallback | 250 m |

Examples: a 60 × 25 m church ~17 m, a 300 × 200 m castle ~91 m, a 500 m
bridge ~125 m. A merged duplicate keeps the kept record's position and `p`,
so a merge never lowers `p`.

### Weight `w`

`base(kind) × 1.2 if a Wikidata id exists × size bonus`, clamped to 0.5–2.0.
Base: peak with elevation 1.5, other terrain 1.2; cathedral, communication
tower, observation tower, lighthouse, tall building 1.3; church, castle,
tower 1.1; chapel 0.6; everything else 1.0. Size bonus: structures with
height ≥ 50 m × 1.2, ≥ 100 m × 1.4.

## Selection rules (from the spike, with its fixes)

Per 1° cell, from Overture (release pinned per build):

1. `base/land`, named, class `peak|hill|volcano`.
2. `base/infrastructure`: named with class `communication_tower|bell_tower|
   water_tower|observation|watchtower|minaret|lighthouse|radar|cooling|
   gasometer|dam`; or named with `source_tags.man_made` in
   `tower|mast|communications_tower|lighthouse|windmill|chimney|water_tower`;
   or named with `source_tags.historic` in `castle|ruins|fort|tower`; or class
   `communication_tower|mobile_phone_tower` with height ≥ 50 m (name
   "Communication tower"); or class `bridge` with Wikidata id and a name
   ending in `brücke|bridge|viadukt|viaduct` (bridges often carry the
   street's name and Wikidata id, which are not landmarks).
3. `buildings/building`: named with class `church|cathedral|chapel|mosque|
   synagogue|temple|monastery|castle|tower`; or named with a castle word
   (see *Name words* below) from `schloss|burg|castle|palace|palais|festung|
   kloster|abtei`; or height ≥ 80 m (name "Tall building" when unnamed).
4. `places/place`, named: `castle|fort|monument|lighthouse|memorial_site` with
   confidence ≥ 0.6; `historic_site` with confidence ≥ 0.6 and a name word from
   `burg|schloss|castle|turm|tower|warte|kastell|ruine|ruin|fort|kloster|abbey|abtei`;
   `christian_place_of_worship` with confidence ≥ 0.7 **only if no buildings-theme
   church lies within 250 m**; `mountain` with confidence ≥ 0.8 **only if no
   land peak shares the normalised name within 2 km** and the name has no " - ".
5. Dedupe: same normalised name (NFKD, ASCII fold, lower-case, punctuation to
   spaces) within 400 m merges into one feature; keep the first by provenance
   land > infrastructure > buildings > places and fill missing `e`/Wikidata
   from the others.

*Name words.* Names are split into case-folded words (a trailing
parenthesis ignored). A keyword matches a whole word or the end of a compound
(`Wasserschloss`, `Bismarckwarte`), never a prefix or the middle of a word, so
"Schlosserei", "Burger King" and "Schlossstraße" stay out. A word merely ending
in `burg` counts only when it is the whole name (`Marienburg`), because German
place names end in -burg: "Bahnhof Nienburg" and "Amtsgericht Burgwedel" stay
out. The kind follows the keyword: castle words → `castle`,
`festung|kastell|fort` → `fort`, `ruine|ruin` → `ruins`,
`kloster|abbey|abtei` → `monastery`, `turm|tower|warte` → `tower`. Plain
substrings, as first written, made 278 of 1,899 features in cell 52_9 "castles",
mostly shops and offices; words bring it to 95 real ones.

Excluded on purpose: viewpoints (places to stand, not targets), generic
tourist attractions, sports venues.

## Build

- Read Overture GeoParquet anonymously from `s3://overturemaps-us-west-2`
  with DuckDB (`httpfs`, `spatial`). Pick only the files whose STAC extent
  (`https://stac.overturemaps.org/<release>/<theme>/<type>/collection.json`)
  intersects the coverage; never scan a whole theme.
- Coverage cells: all 1° cells intersecting the DE or AT country polygons from
  Overture `divisions/division_area` of the same release (class `land`).
- Positions are Overture bounding-box centres, which are exact for points but
  not polygon centroids; the bbox extent and the source give `p` (above).
  This keeps the large `geometry` column out of every download except the
  country polygons.
- Output to `public/`, validate every file against this contract (schema,
  kinds, bounds, size, sorting) and the whole set against `index.json`.
- Publish by force-pushing the contents of `public/` to the orphan branch
  `pages`, which Cloudflare Pages deploys (no build command, output = branch
  root). History on `pages` is never kept, so the repository does not grow.
- Schedule: a weekly GitHub Actions check builds within a week of each
  monthly Overture release, plus manual dispatch. A build that fails
  validation publishes nothing.

`public/_headers`:

```
/v1/index.json
  Cache-Control: public, max-age=3600
  Access-Control-Allow-Origin: *
/v1/*/cells/*
  Cache-Control: public, max-age=31536000, immutable
  Access-Control-Allow-Origin: *
```

### Running it

```
pip install -r requirements.txt            # DuckDB 1.5.5, pygeomag 1.1.0 (WMM)
python -m unittest discover -s tests -t .  # rules, cell writer, validator
python -m aime_data.build --cells 52_9     # one cell, for a local check
python -m aime_data.build                  # full build, latest release
python -m aime_data.validate public
scripts/publish.sh public --dry-run
```

`work/` caches the extracts per release, so a re-run after a rule change
re-selects without downloading. The build writes `work/report.md` and
`work/report.json`: counts per theme and kind, the largest cell, the spread of
`p`, and which of
the known landmarks in `aime_data/landmarks.py` (the spike's lists plus
Hannover) are present. A missing known landmark is a warning for review, not
a failure. `scripts/publish.sh` keeps the previously published
dataset and drops older ones (`aime_data/publish.py` plans it): an identical
rebuild is a no-op, changed bytes for a published Overture release become the
next revision, and an older release is refused.

GitHub Actions (`.github/workflows/build.yml`): unit tests on every push and
pull request; a one-cell smoke build against Overture on pull requests; the
publish job runs on manual dispatch (optional release, optional force) and
weekly, building only when Overture's latest release is not on `pages` yet.

## Privacy

Aimé downloads `index.json` and the 1° cells its search radius touches. The
data host therefore learns roughly which 110 × 70 km area a user looks at,
not the viewpoint, radius or photo. No cookies, no query strings, no logs
beyond Cloudflare's standard edge logs.
