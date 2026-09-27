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
  v1/
    index.json
    <release>/cells/<lat>_<lon>.json
```

- `<release>` is the Overture release, e.g. `2026-09-23.1`. Paths under a
  release never change once published.
- A cell covers `lat ≤ φ < lat+1`, `lon ≤ λ < lon+1`; names use the integer
  south-west corner, e.g. `50_8.json`, `47_-1.json`, `-34_18.json`.
- Only non-empty cells are written; `index.json` lists them.
- The current and the previous release are kept; older releases are removed.

### `v1/index.json`

```json
{
  "schema": 1,
  "release": "2026-09-23.1",
  "built": "2026-09-27T12:00:00Z",
  "cellDeg": 1,
  "coverage": ["DE", "AT"],
  "path": "2026-09-23.1/cells/",
  "cells": ["46_9", "46_10", "47_5"],
  "license": "ODbL-1.0",
  "attribution": "© OpenStreetMap contributors, Overture Maps Foundation",
  "kinds": { "peak": { "placementM": 8 }, "church": { "placementM": 25 } }
}
```

`kinds` lists every kind that can appear, with its placement precision in
metres. The module uses `placementM` as the landmark's position uncertainty
in the solver.

### `v1/<release>/cells/<lat>_<lon>.json`

```json
{
  "schema": 1,
  "release": "2026-09-23.1",
  "cell": [50, 8],
  "f": [["Großer Feldberg", "peak", 50.23237, 8.45694, 879, 1.8]]
}
```

Each feature is `[name, kind, lat, lon, e, w]`:

| Field | Meaning |
| --- | --- |
| `name` | Primary name, NFC, at most 80 characters, never empty |
| `kind` | One of the kinds below |
| `lat`, `lon` | WGS84 degrees, 5 decimals (point or building centroid) |
| `e` | Elevation above sea level in metres for peak/hill/volcano; structure height in metres for everything else; `0` when unknown |
| `w` | Visibility weight, 0.5–2.0, one decimal (see below) |

A cell file must stay under **1 MiB** of JSON; the build fails otherwise (the
host caps JSON responses at 2 MiB). Features are sorted by `w` descending,
then name, for stable diffs.

### Kinds and placement precision

| Group | Kinds | `placementM` |
| --- | --- | --- |
| Terrain points | `peak`, `hill`, `volcano` | 8 |
| Structure points | `tower`, `observation`, `communication_tower`, `mast`, `bell_tower`, `water_tower`, `watchtower`, `minaret`, `lighthouse`, `windmill`, `chimney`, `radar` | 8 |
| Building centroids | `church`, `cathedral`, `chapel`, `mosque`, `synagogue`, `temple`, `monastery`, `castle`, `ruins`, `fort`, `tall_building`, `gasometer`, `cooling` | 25 |
| Places-derived points | `monument`, `memorial` (and `castle`/`church` when only in places) | 30 |
| Large structures | `bridge`, `dam` | 50 |

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
   "Communication tower"); or class `bridge` with name and Wikidata id.
3. `buildings/building`: named with class `church|cathedral|chapel|mosque|
   synagogue|temple|monastery|castle|tower`; or named and matching
   `schloss|burg|castle|palace|palais|festung|kloster|abtei` (case-insensitive);
   or height ≥ 80 m (name "Tall building" when unnamed).
4. `places/place`, named: `castle|fort|monument|lighthouse|memorial_site` with
   confidence ≥ 0.6; `historic_site` with confidence ≥ 0.6 and a name matching
   `burg|schloss|castle|turm|tower|warte|kastell|ruine|ruin|fort|kloster|abbey|abtei`;
   `christian_place_of_worship` with confidence ≥ 0.7 **only if no buildings-theme
   church lies within 250 m**; `mountain` with confidence ≥ 0.8 **only if no
   land peak shares the normalised name within 2 km** and the name has no " - ".
5. Dedupe: same normalised name (NFKD, ASCII fold, lower-case, punctuation to
   spaces) within 400 m merges into one feature; keep the first by provenance
   land > infrastructure > buildings > places and fill missing `e`/Wikidata
   from the others.

Excluded on purpose: viewpoints (places to stand, not targets), generic
tourist attractions, sports venues.

## Build

- Read Overture GeoParquet anonymously from `s3://overturemaps-us-west-2`
  with DuckDB (`httpfs`, `spatial`). Pick only the files whose STAC extent
  (`https://stac.overturemaps.org/<release>/<theme>/<type>/collection.json`)
  intersects the coverage; never scan a whole theme.
- Coverage cells: all 1° cells intersecting the DE or AT country polygons from
  Overture `divisions/division_area` of the same release.
- Output to `public/`, validate every file against this contract (schema,
  kinds, bounds, size, sorting) and the whole set against `index.json`.
- Publish by force-pushing the contents of `public/` to the orphan branch
  `pages`, which Cloudflare Pages deploys (no build command, output = branch
  root). History on `pages` is never kept, so the repository does not grow.
- Schedule: monthly GitHub Actions run a few days after each Overture release,
  plus manual dispatch. A build that fails validation publishes nothing.

`public/_headers`:

```
/v1/index.json
  Cache-Control: public, max-age=3600
  Access-Control-Allow-Origin: *
/v1/*/cells/*
  Cache-Control: public, max-age=31536000, immutable
  Access-Control-Allow-Origin: *
```

## Privacy

Aimé downloads `index.json` and the 1° cells its search radius touches. The
data host therefore learns roughly which 110 × 70 km area a user looks at,
not the viewpoint, radius or photo. No cookies, no query strings, no logs
beyond Cloudflare's standard edge logs.
