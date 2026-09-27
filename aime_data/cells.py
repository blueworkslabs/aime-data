"""Cell grouping and the files under public/ (README "Layout")."""
import json
import math
import os

from . import contract as C
from .rules import record


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def cell_of(rec):
    """Cell of a compact record, from its rounded coordinates."""
    return math.floor(rec[2]), math.floor(rec[3])


def record_order(rec):
    return (-rec[5], rec[0], rec[1], rec[2], rec[3])


def group(features, coverage_cells):
    """Compact records per coverage cell, sorted by w descending, then name.
    Features outside the coverage cells are dropped."""
    out = {}
    for f in features:
        rec = record(f)
        cell = cell_of(rec)
        if cell in coverage_cells:
            out.setdefault(cell, []).append(rec)
    for recs in out.values():
        recs.sort(key=record_order)
    return out


def write(public, release, built, grouped, coverage=C.COVERAGE):
    """Write v1/index.json, the release's cells, _headers and index.html.
    Returns the index dict. Raises if a cell reaches MAX_CELL_BYTES."""
    rel_dir = os.path.join(public, "v1", release, "cells")
    os.makedirs(rel_dir, exist_ok=True)
    names = []
    for (lat, lon) in sorted(grouped):
        name = C.cell_name(lat, lon)
        body = dumps({"schema": C.SCHEMA, "release": release, "cell": [lat, lon], "f": grouped[(lat, lon)]})
        data = body.encode()
        if len(data) >= C.MAX_CELL_BYTES:
            raise ValueError(f"cell {name} is {len(data)} bytes, limit {C.MAX_CELL_BYTES}")
        with open(os.path.join(rel_dir, name + ".json"), "wb") as fh:
            fh.write(data)
        names.append(name)
    index = {
        "schema": C.SCHEMA,
        "release": release,
        "built": built,
        "cellDeg": C.CELL_DEG,
        "coverage": list(coverage),
        "path": f"{release}/cells/",
        "cells": names,
        "license": C.LICENSE,
        "attribution": C.ATTRIBUTION,
        "kinds": C.KINDS,
    }
    with open(os.path.join(public, "v1", "index.json"), "w", encoding="utf-8") as fh:
        fh.write(dumps(index))
    with open(os.path.join(public, "_headers"), "w", encoding="utf-8") as fh:
        fh.write(C.HEADERS)
    with open(os.path.join(public, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(LANDING.format(release=release, built=built, cells=len(names),
                                features=sum(len(v) for v in grouped.values()),
                                coverage=", ".join(coverage), attribution=C.ATTRIBUTION))
    return index


LANDING = """<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Aimé landmark data</title>
<style>body{{font:16px/1.5 system-ui,sans-serif;max-width:40rem;margin:2rem auto;padding:0 1rem}}</style>
<h1>Aimé landmark data</h1>
<p>Pre-built landmark cells for the Aimé module of
<a href="https://github.com/blueworkslabs/construct">Construct</a>.
Release {release}, built {built}: {features} landmarks in {cells} cells of 1°, coverage {coverage}.</p>
<p>Data: {attribution}. Licensed under the
<a href="https://opendatacommons.org/licenses/odbl/1-0/">Open Database License 1.0</a>.
Index: <a href="v1/index.json">v1/index.json</a>.</p>
"""
