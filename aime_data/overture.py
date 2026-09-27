"""Reading Overture Maps: STAC file selection and DuckDB extraction.

Only the Parquet files whose STAC extent intersects the coverage are read,
never a whole theme.
Positions are bounding-box centres, so the large `geometry` column is never
downloaded except for the country polygons. A bbox centre is exact for points
but not a polygon centroid; the bbox extent feeds each feature's position
uncertainty `p` instead of any claim about centroid distance.
"""
import json
import hashlib
import math
import os
import time
import urllib.request

STAC = "https://stac.overturemaps.org"
TIMEOUT = 60


def get_json(url, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "aime-data-pipeline (github.com/blueworkslabs/aime-data)"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return json.load(r)
        except OSError:
            if i == tries - 1:
                raise
            time.sleep(2 ** i)


def latest_release():
    return get_json(f"{STAC}/catalog.json")["latest"]


def files(release, theme, typ, box):
    """Parquet URLs of <theme>/<type> whose STAC extent intersects box (x0, y0, x1, y1)."""
    x0, y0, x1, y1 = box
    col = get_json(f"{STAC}/{release}/{theme}/{typ}/collection.json")
    extents = col["extent"]["spatial"]["bbox"][1:]
    items = [link["href"] for link in col["links"] if link["rel"] == "item"]
    if len(extents) != len(items):
        raise ValueError(f"{theme}/{typ}: {len(extents)} extents for {len(items)} items")
    out = []
    for e, href in zip(extents, items):
        if e[0] <= x1 and e[2] >= x0 and e[1] <= y1 and e[3] >= y0:
            hrefs = [a["href"] for a in get_json(href)["assets"].values() if a["href"].endswith(".parquet")]
            s3 = [h for h in hrefs if h.startswith("s3://")]
            out.append((s3 or hrefs)[0])
    if not out:
        raise ValueError(f"{theme}/{typ}: no files intersect {box}")
    return out


def connect(work, memory="4GB", threads=4):
    import duckdb
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;")
    tmp = os.path.join(work, "duck-tmp")
    os.makedirs(tmp, exist_ok=True)
    con.execute(f"SET memory_limit='{memory}'; SET threads={int(threads)}; SET preserve_insertion_order=false;")
    con.execute(f"SET temp_directory='{tmp}';")
    con.execute("CREATE OR REPLACE SECRET overture (TYPE s3, PROVIDER config, REGION 'us-west-2');")
    return con


def source(release, theme, typ, box):
    urls = ",".join(f"'{u}'" for u in files(release, theme, typ, box))
    return f"read_parquet([{urls}], hive_partitioning=false)"


def in_box(box):
    x0, y0, x1, y1 = box
    return f"bbox.xmin <= {x1} AND bbox.xmax >= {x0} AND bbox.ymin <= {y1} AND bbox.ymax >= {y0}"


def sql_list(values):
    return ",".join(f"'{v}'" for v in values)


def coverage_cells(con, release, countries, box):
    """1° cells (lat, lon) that intersect the land polygon of any country.
    `box` only narrows the STAC file selection; it must contain the countries."""
    src = source(release, "divisions", "division_area", box)
    rows = con.execute(f"""
        SELECT country, ST_AsWKB(geometry) AS wkb, bbox FROM {src}
        WHERE subtype = 'country' AND class = 'land' AND country IN ({sql_list(countries)})""").fetchall()
    found = {r[0] for r in rows}
    if found != set(countries):
        raise ValueError(f"country polygons missing: {sorted(set(countries) - found)}")
    con.execute("CREATE OR REPLACE TEMP TABLE countries (geom GEOMETRY)")
    cells = set()
    for _, wkb, bb in rows:
        con.execute("DELETE FROM countries")
        con.execute("INSERT INTO countries SELECT ST_GeomFromWKB(?)", [wkb])
        cand = [(lat, lon) for lat in range(math.floor(bb["ymin"]), math.floor(bb["ymax"]) + 1)
                for lon in range(math.floor(bb["xmin"]), math.floor(bb["xmax"]) + 1)]
        for lat, lon in cand:
            hit = con.execute(
                "SELECT ST_Intersects(geom, ST_MakeEnvelope(?, ?, ?, ?)) FROM countries",
                [lon, lat, lon + 1, lat + 1]).fetchone()[0]
            if hit:
                cells.add((lat, lon))
    return cells


def box_of(cells):
    lats = [c[0] for c in cells]
    lons = [c[1] for c in cells]
    return (min(lons), min(lats), max(lons) + 1, max(lats) + 1)


# Bbox centre as the position and bbox extent (degrees) for the position
# uncertainty p (rules.uncertainty).
CENTRE = ("(bbox.xmin + bbox.xmax) / 2 AS lon, (bbox.ymin + bbox.ymax) / 2 AS lat, "
          "bbox.xmax - bbox.xmin AS dx, bbox.ymax - bbox.ymin AS dy")

# SQL pre-filters are supersets of the rules in rules.py, which decide exactly.
QUERIES = {
    "land": ("base", "land", """
        SELECT names.primary AS name, class AS cls, elevation, wikidata, {centre}
        FROM {src} WHERE {box} AND names.primary IS NOT NULL AND class IN ('peak', 'hill', 'volcano')"""),
    "infra": ("base", "infrastructure", """
        SELECT names.primary AS name, class AS cls, height, wikidata,
               source_tags['man_made'] AS man_made, source_tags['historic'] AS historic, {centre}
        FROM {src} WHERE {box} AND (
          (names.primary IS NOT NULL AND (
             class IN ('communication_tower', 'bell_tower', 'water_tower', 'observation', 'watchtower',
                       'minaret', 'lighthouse', 'radar', 'cooling', 'gasometer', 'dam')
             OR source_tags['man_made'] IN ('tower', 'mast', 'communications_tower', 'lighthouse',
                                            'windmill', 'chimney', 'water_tower')
             OR source_tags['historic'] IN ('castle', 'ruins', 'fort', 'tower')
             OR (class = 'bridge' AND wikidata IS NOT NULL)))
          OR (class IN ('communication_tower', 'mobile_phone_tower') AND height >= 50)
          -- Unnamed tower points anchor the tower snap; unnamed chimneys and
          -- cooling towers of 80 m or more are landmarks of their own.
          OR class IN ('observation', 'bell_tower', 'communication_tower', 'watchtower', 'minaret', 'cooling')
          OR source_tags['man_made'] IN ('tower', 'communications_tower', 'chimney', 'cooling_tower'))"""),
    "buildings": ("buildings", "building", """
        SELECT names.primary AS name, class AS cls, height, {centre}
        FROM {src} WHERE {box} AND (
          (names.primary IS NOT NULL AND (
             class IN ('church', 'cathedral', 'chapel', 'mosque', 'synagogue', 'temple', 'monastery', 'castle', 'tower')
             OR regexp_matches(names.primary, 'schloss|schloß|burg|castle|palace|palais|festung|kloster|abtei', 'i')))
          OR height >= 50)"""),
    "places": ("places", "place", """
        SELECT names.primary AS name, basic_category AS category, confidence, {centre}
        FROM {src} WHERE {box} AND names.primary IS NOT NULL AND confidence >= 0.6
          AND (basic_category IN ('castle', 'fort', 'monument', 'lighthouse', 'memorial_site',
                                  'historic_site', 'christian_place_of_worship', 'mountain')
               OR (basic_category IN ('power_plant', 'electric_utility_provider', 'campus_building',
                                      'public_utility_provider')
                   AND regexp_matches(names.primary, 'kraftwerk|power (station|plant)', 'i')))"""),
}


def extract(con, release, box, work, log=print):
    """Extract each theme's candidate rows to <work>/<theme>.parquet (reused when
    present) and return {theme: [row dict, ...]}."""
    rows = {}
    for key, (theme, typ, sql) in QUERIES.items():
        # Both coverage and extraction SQL determine cache contents. A wider
        # follow-up build must never reuse an earlier region's partial rows.
        signature = hashlib.sha256(json.dumps([release, box, CENTRE, sql], sort_keys=True).encode()).hexdigest()[:20]
        out = os.path.join(work, f"{key}-{signature}.parquet")
        if not os.path.exists(out):
            t = time.time()
            q = sql.format(centre=CENTRE, src=source(release, theme, typ, box), box=in_box(box))
            con.execute(f"COPY ({q}) TO '{out}.part' (FORMAT parquet)")
            os.replace(out + ".part", out)
            log(f"extract {key}: {time.time() - t:.0f}s")
        cur = con.execute(f"SELECT * FROM '{out}'")
        names = [d[0] for d in cur.description]
        rows[key] = [dict(zip(names, r)) for r in cur.fetchall()]
        log(f"extract {key}: {len(rows[key])} candidate rows")
    return rows
