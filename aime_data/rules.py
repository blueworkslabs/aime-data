"""Selection rules, dedupe and weights (README "Selection rules" and "Weight").

Pure Python over plain row dicts so the rules are unit-tested without DuckDB or
the network. Each theme function takes one extracted row and returns a feature
dict or None; `select` applies the cross-theme rules and the dedupe.

Row shapes (see extract.py):
  land       {name, cls, elevation, wikidata, lat, lon}
  infra      {name, cls, height, wikidata, man_made, historic, lat, lon}
  buildings  {name, cls, height, lat, lon}
  places     {name, category, confidence, lat, lon}
"""
import math
import re
import unicodedata

from .contract import KINDS, NAME_MAX, TERRAIN, W_MAX, W_MIN

PROVENANCE = ("land", "infra", "buildings", "places")

INFRA_CLASSES = (
    "communication_tower", "bell_tower", "water_tower", "observation", "watchtower",
    "minaret", "lighthouse", "radar", "cooling", "gasometer", "dam",
)
MAN_MADE = {
    "tower": "tower", "mast": "mast", "communications_tower": "communication_tower",
    "lighthouse": "lighthouse", "windmill": "windmill", "chimney": "chimney",
    "water_tower": "water_tower",
}
HISTORIC = {"castle": "castle", "ruins": "ruins", "fort": "fort", "tower": "tower"}
MAST_CLASSES = ("communication_tower", "mobile_phone_tower")
BUILDING_CLASSES = (
    "church", "cathedral", "chapel", "mosque", "synagogue", "temple", "monastery",
    "castle", "tower",
)
PLACES_KINDS = {
    "castle": "castle", "fort": "fort", "monument": "monument",
    "lighthouse": "lighthouse", "memorial_site": "memorial",
}
CHURCH_KINDS = ("church", "cathedral", "chapel")

# Name keywords match whole words or the end of a compound ("Wasserschloss",
# "Bismarckwarte"), never a prefix: plain substrings pulled in "Burger King",
# "Schlosserei" and every building named after Nienburg or Burgwedel. A word
# merely ending in "burg" counts only when it is the whole name
# ("Marienburg"), because German place names end in -burg all the time.
BUILDING_WORDS = ("schloss", "burg", "castle", "palace", "palais", "festung", "kloster", "abtei")
HISTORIC_SITE_WORDS = ("burg", "schloss", "castle", "turm", "tower", "warte", "kastell", "ruine",
                       "ruin", "fort", "kloster", "abbey", "abtei")
# First matching group decides the kind.
WORD_KINDS = (
    (("burg", "schloss", "castle", "palace", "palais"), "castle"),
    (("festung", "kastell", "fort"), "fort"),
    (("ruine", "ruin"), "ruins"),
    (("kloster", "abbey", "abtei"), "monastery"),
    (("turm", "tower", "warte"), "tower"),
)
BRIDGE_WORDS = ("brücke", "bruecke", "bridge", "viadukt", "viaduct")

CHURCH_CLEARANCE_M = 250
MOUNTAIN_CLEARANCE_M = 2000
DEDUPE_M = 400


def norm(s):
    """NFKD, ASCII fold, lower-case, punctuation to spaces."""
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def clean_name(s):
    """Primary name, NFC, at most NAME_MAX characters; None when empty."""
    if s is None:
        return None
    s = " ".join(unicodedata.normalize("NFC", str(s)).split())
    s = s[:NAME_MAX].rstrip()
    return s or None


def num(v):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else v


def feature(name, kind, row, src, e=None, wikidata=None):
    assert kind in KINDS, kind
    return {"name": name, "kind": kind, "lat": row["lat"], "lon": row["lon"], "e": num(e),
            "wikidata": wikidata or None, "src": src}


def land(row):
    name = clean_name(row.get("name"))
    if name and row.get("cls") in TERRAIN:
        return feature(name, row["cls"], row, "land", row.get("elevation"), row.get("wikidata"))


def infra(row):
    name, cls = clean_name(row.get("name")), row.get("cls")
    mm, hi, h = row.get("man_made"), row.get("historic"), num(row.get("height"))
    kind = None
    if name and cls in INFRA_CLASSES:
        kind = cls
    elif name and mm in MAN_MADE:
        kind = MAN_MADE[mm]
    elif name and hi in HISTORIC:
        kind = HISTORIC[hi]
    elif cls in MAST_CLASSES and h is not None and h >= 50:
        kind, name = "communication_tower", name or "Communication tower"
    elif cls == "bridge" and name and row.get("wikidata") and any(
            w.endswith(b) for w in words(name) for b in BRIDGE_WORDS):
        kind = "bridge"
    if kind:
        return feature(name, kind, row, "infra", h, row.get("wikidata"))


def words(name):
    """Lower-case words of a name, ignoring a trailing parenthesis."""
    return re.findall(r"[^\W\d_]+", re.sub(r"\s*\(.*\)\s*$", "", name).casefold())


def keyword(name, allowed):
    """The keyword of `allowed` that the name carries, or None."""
    ws = words(name)
    for w in ws:
        for k in allowed:
            if w == k or (k != "burg" and w.endswith(k)) or (k == "burg" and len(ws) == 1 and w.endswith(k)):
                return k
    return None


def name_kind(name, allowed):
    k = keyword(name, allowed)
    return next((kind for group, kind in WORD_KINDS if k in group), None)


def buildings(row):
    name, cls, h = clean_name(row.get("name")), row.get("cls"), num(row.get("height"))
    if name and cls in BUILDING_CLASSES:
        return feature(name, cls, row, "buildings", h)
    kind = name and name_kind(name, BUILDING_WORDS)
    if kind:
        return feature(name, kind, row, "buildings", h)
    if h is not None and h >= 80:
        return feature(name or "Tall building", "tall_building", row, "buildings", h)


def places(row):
    """Unconditional places rules; the church and mountain rules need the other
    themes and are resolved in `select`."""
    name, cat, conf = clean_name(row.get("name")), row.get("category"), num(row.get("confidence")) or 0
    if not name:
        return None
    if cat in PLACES_KINDS and conf >= 0.6:
        return feature(name, PLACES_KINDS[cat], row, "places")
    kind = cat == "historic_site" and conf >= 0.6 and name_kind(name, HISTORIC_SITE_WORDS)
    if kind:
        return feature(name, kind, row, "places")
    if cat == "christian_place_of_worship" and conf >= 0.7:
        return feature(name, "church", row, "places:church")
    if cat == "mountain" and conf >= 0.8 and " - " not in name:
        return feature(name, "peak", row, "places:mountain")


def metres(a, b):
    """Equirectangular distance in metres; exact enough below a few km."""
    dy = (a["lat"] - b["lat"]) * 111_195
    dx = (a["lon"] - b["lon"]) * 111_195 * math.cos(math.radians((a["lat"] + b["lat"]) / 2))
    return math.hypot(dx, dy)


class Near:
    """Grid index of features for radius queries up to 3 km."""

    STEP = 0.05  # degrees; one bucket is ≥ 3.1 km in both axes below 55.9° N

    def __init__(self, features=(), key=None):
        self.key, self.grid = key, {}
        for f in features:
            self.add(f)

    def _bucket(self, f):
        return math.floor(f["lat"] / self.STEP), math.floor(f["lon"] / self.STEP)

    def add(self, f):
        k = self.key(f) if self.key else None
        by, bx = self._bucket(f)
        self.grid.setdefault((k, by, bx), []).append(f)

    def find(self, f, radius_m, key=None):
        assert radius_m <= 3000
        by, bx = self._bucket(f)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                for g in self.grid.get((key, by + dy, bx + dx), ()):
                    if metres(f, g) < radius_m:
                        return g
        return None


def weight(f):
    """base(kind) × 1.2 with Wikidata × size bonus, clamped 0.5–2.0, one decimal."""
    k, e = f["kind"], f["e"]
    if k in TERRAIN:
        base = 1.5 if k == "peak" and e else 1.2
    elif k in ("cathedral", "communication_tower", "observation", "lighthouse", "tall_building"):
        base = 1.3
    elif k in ("church", "castle", "tower"):
        base = 1.1
    elif k == "chapel":
        base = 0.6
    else:
        base = 1.0
    w = base * (1.2 if f["wikidata"] else 1.0)
    if k not in TERRAIN and e:
        w *= 1.4 if e >= 100 else 1.2 if e >= 50 else 1.0
    return round(min(W_MAX, max(W_MIN, w)), 1)


def sort_key(f):
    return (f["name"], f["kind"], f["lat"], f["lon"])


def select(rows):
    """rows: {"land": [...], "infra": [...], "buildings": [...], "places": [...]}.
    Returns (features, stats). Output order is deterministic."""
    theme_fns = {"land": land, "infra": infra, "buildings": buildings, "places": places}
    picked = {src: sorted(filter(None, map(fn, rows.get(src, ()))), key=sort_key)
              for src, fn in theme_fns.items()}
    stats = {"candidates": {src: len(v) for src, v in picked.items()}}

    churches = Near(f for f in picked["buildings"] if f["kind"] in CHURCH_KINDS)
    peaks = Near((f for f in picked["land"] if f["kind"] in TERRAIN), key=lambda f: norm(f["name"]))
    kept_places, dropped = [], {"places:church": 0, "places:mountain": 0}
    for f in picked["places"]:
        if f["src"] == "places:church" and churches.find(f, CHURCH_CLEARANCE_M):
            dropped[f["src"]] += 1
            continue
        if f["src"] == "places:mountain" and peaks.find(f, MOUNTAIN_CLEARANCE_M, norm(f["name"])):
            dropped[f["src"]] += 1
            continue
        kept_places.append(dict(f, src="places"))
    picked["places"] = kept_places
    stats["places_dropped_near_theme_twin"] = dropped

    # Dedupe: same normalised name within 400 m; the first by provenance wins and
    # fills its missing elevation/height and Wikidata id from the others.
    kept, index, merged = [], Near(key=lambda f: norm(f["name"])), 0
    for src in PROVENANCE:
        for f in picked[src]:
            twin = index.find(f, DEDUPE_M, norm(f["name"]))
            if twin:
                twin["e"] = twin["e"] if twin["e"] else f["e"]
                twin["wikidata"] = twin["wikidata"] or f["wikidata"]
                merged += 1
                continue
            index.add(f)
            kept.append(f)
    stats["merged"] = merged
    for f in kept:
        f["w"] = weight(f)
    stats["features"] = len(kept)
    return kept, stats


def record(f):
    """Compact contract record [name, kind, lat, lon, e, w]."""
    e = f["e"]
    return [f["name"], f["kind"], round(f["lat"], 5), round(f["lon"], 5),
            int(round(e)) if e else 0, f["w"]]
