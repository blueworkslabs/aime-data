"""Validate public/ against the data contract, schema 1.

    python -m aime_data.validate public

Checks the index, every cell file of the index's release (schema, release,
cell id, record shape, kinds, bounds, precision, weights, sorting, size) and
that the set of cell files matches `index.cells` exactly.
"""
import json
import math
import os
import re
import sys
import unicodedata

from . import contract as C
from .cells import record_order

RELEASE = re.compile(r"^\d{4}-\d{2}-\d{2}\.\d+$")
CELL = re.compile(r"^(-?\d+)_(-?\d+)$")
INDEX_KEYS = {"schema", "release", "built", "cellDeg", "coverage", "path", "cells", "license", "attribution", "kinds"}


def read(path, mode="r"):
    with open(path, mode, **({} if "b" in mode else {"encoding": "utf-8"})) as fh:
        return fh.read()


def decimals_ok(x, places):
    return abs(round(x, places) - x) < 10 ** -(places + 3)


def check_record(rec, kinds, lat0, lon0):
    if not isinstance(rec, list) or len(rec) != 6:
        return "record is not a 6-element array"
    name, kind, lat, lon, e, w = rec
    if not isinstance(name, str) or not name.strip():
        return "empty name"
    if len(name) > C.NAME_MAX:
        return f"name longer than {C.NAME_MAX}"
    if unicodedata.normalize("NFC", name) != name:
        return "name not NFC"
    if kind not in kinds:
        return f"unknown kind {kind!r}"
    for v in (lat, lon, e, w):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            return "non-numeric field"
    if not (lat0 <= lat < lat0 + C.CELL_DEG and lon0 <= lon < lon0 + C.CELL_DEG):
        return f"position {lat},{lon} outside the cell"
    if not (decimals_ok(lat, 5) and decimals_ok(lon, 5)):
        return "position has more than 5 decimals"
    if not isinstance(e, int):
        return "e is not an integer"
    if not (C.W_MIN <= w <= C.W_MAX) or not decimals_ok(w, 1):
        return f"weight {w} outside 0.5–2.0 or not one decimal"
    return None


def validate_cell(path, index):
    """Returns a list of error strings for one cell file."""
    name = os.path.basename(path)[:-5]
    m = CELL.match(name)
    if not m:
        return [f"{name}: bad cell file name"]
    lat0, lon0 = int(m.group(1)), int(m.group(2))
    raw = read(path, "rb")
    errs = []
    if len(raw) >= C.MAX_CELL_BYTES:
        errs.append(f"{name}: {len(raw)} bytes, limit {C.MAX_CELL_BYTES}")
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        return errs + [f"{name}: not JSON ({e})"]
    if not isinstance(doc, dict) or set(doc) != {"schema", "release", "cell", "f"}:
        return errs + [f"{name}: keys must be schema, release, cell, f"]
    if doc["schema"] != C.SCHEMA:
        errs.append(f"{name}: schema {doc['schema']!r}")
    if doc["release"] != index["release"]:
        errs.append(f"{name}: release {doc['release']!r} does not match the index")
    if doc["cell"] != [lat0, lon0]:
        errs.append(f"{name}: cell {doc['cell']!r} does not match the file name")
    f = doc["f"]
    if not isinstance(f, list) or not f:
        return errs + [f"{name}: f must be a non-empty array"]
    for i, rec in enumerate(f):
        err = check_record(rec, index["kinds"], lat0, lon0)
        if err:
            errs.append(f"{name}: f[{i}]: {err}")
            if len(errs) > 20:
                break
    if not errs and f != sorted(f, key=record_order):
        errs.append(f"{name}: features not sorted by w descending, then name")
    return errs


def validate_index(index):
    errs = []
    if not isinstance(index, dict) or set(index) != INDEX_KEYS:
        return [f"index: keys must be {sorted(INDEX_KEYS)}"]
    if index["schema"] != C.SCHEMA:
        errs.append(f"index: schema {index['schema']!r}")
    if not isinstance(index["release"], str) or not RELEASE.match(index["release"]):
        errs.append(f"index: release {index['release']!r}")
    if index["cellDeg"] != C.CELL_DEG:
        errs.append("index: cellDeg")
    if index["path"] != f"{index['release']}/cells/":
        errs.append("index: path must be <release>/cells/")
    if index["license"] != C.LICENSE or index["attribution"] != C.ATTRIBUTION:
        errs.append("index: licence or attribution")
    kinds = index["kinds"]
    if not isinstance(kinds, dict) or not kinds or not all(
            isinstance(v, dict) and isinstance(v.get("placementM"), (int, float)) and v["placementM"] > 0
            for v in kinds.values()):
        errs.append("index: kinds must map each kind to {placementM > 0}")
    elif kinds != C.KINDS:
        errs.append("index: kinds differ from the contract table")
    if not isinstance(index["coverage"], list) or not index["coverage"] or not all(
            isinstance(c, str) and re.match(r"^[A-Z]{2}$", c) for c in index["coverage"]):
        errs.append("index: coverage must list ISO country codes")
    if not isinstance(index["built"], str) or not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", index["built"]):
        errs.append("index: built must be an ISO UTC timestamp")
    cells = index["cells"]
    if not isinstance(cells, list) or not cells or not all(isinstance(c, str) and CELL.match(c) for c in cells):
        errs.append("index: cells must be a non-empty list of <lat>_<lon>")
    elif len(set(cells)) != len(cells):
        errs.append("index: duplicate cells")
    return errs


def validate(public):
    """Returns (errors, summary)."""
    try:
        index = json.loads(read(os.path.join(public, "v1", "index.json")))
    except (OSError, ValueError) as e:
        return [f"index: {e}"], {}
    errs = validate_index(index)
    if errs:
        return errs, {}
    headers = os.path.join(public, "_headers")
    if not os.path.exists(headers) or read(headers) != C.HEADERS:
        errs.append("_headers missing or different from the contract")
    cell_dir = os.path.join(public, "v1", index["path"])
    on_disk = sorted(n[:-5] for n in os.listdir(cell_dir) if n.endswith(".json")) if os.path.isdir(cell_dir) else []
    listed = sorted(index["cells"])
    for n in sorted(set(listed) - set(on_disk)):
        errs.append(f"{n}: listed in the index but missing")
    for n in sorted(set(on_disk) - set(listed)):
        errs.append(f"{n}: file present but not in the index")
    features, biggest = 0, (0, None)
    for n in sorted(set(listed) & set(on_disk)):
        path = os.path.join(cell_dir, n + ".json")
        cell_errs = validate_cell(path, index)
        errs.extend(cell_errs)
        biggest = max(biggest, (os.path.getsize(path), n))
        if not cell_errs:
            features += len(json.loads(read(path))["f"])
    return errs, {"release": index["release"], "cells": len(listed), "features": features,
                  "largestCell": biggest[1], "largestBytes": biggest[0]}


def main(argv):
    public = argv[1] if len(argv) > 1 else "public"
    errs, summary = validate(public)
    for e in errs[:200]:
        print("ERROR", e)
    if errs:
        print(f"{len(errs)} contract error(s); nothing may be published.")
        return 1
    print("valid:", json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
