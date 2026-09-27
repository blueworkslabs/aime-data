"""Build the landmark cells into public/.

    python -m aime_data.build [--release 2026-09-23.1] [--cells 52_9,52_10]

Steps: coverage cells from the country polygons, STAC-selected extraction,
selection rules, cell files and index, contract validation, build report.
A failed validation exits non-zero, so nothing is published.
"""
import argparse
import datetime
import json
import os
import shutil
import sys
import time

from . import contract as C
from . import overture
from .cells import group, write
from .landmarks import check_known
from .rules import select
from .validate import validate


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def union_box(countries):
    boxes = [C.COUNTRY_BOXES[c] for c in countries]
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def parse_cells(text):
    return {tuple(int(v) for v in c.split("_")) for c in text.split(",") if c}


def percentile(sorted_values, q):
    return sorted_values[min(len(sorted_values) - 1, int(q * len(sorted_values)))] if sorted_values else 0


def report(stats, grouped, index, summary, known):
    by_kind, ps = {}, []
    for cell, recs in grouped.items():
        for r in recs:
            by_kind[r[1]] = by_kind.get(r[1], 0) + 1
            ps.append(r[6])
    ps.sort()
    return {
        "release": index["release"], "dataset": index["dataset"], "built": index["built"], "coverage": index["coverage"],
        "cells": len(index["cells"]), "features": summary["features"],
        "largestCell": summary["largestCell"], "largestBytes": summary["largestBytes"],
        "candidates": stats["candidates"], "mergedDuplicates": stats["merged"],
        "placesDroppedNearThemeTwin": stats["places_dropped_near_theme_twin"],
        "snapped": stats["snapped"],
        "kinds": dict(sorted(by_kind.items(), key=lambda kv: -kv[1])),
        "p": {"p50": percentile(ps, 0.5), "p90": percentile(ps, 0.9), "max": ps[-1] if ps else 0,
              "atLeast100m": sum(1 for v in ps if v >= 100)},
        "knownLandmarks": known,
    }


def markdown(rep):
    lines = [f"## Aimé landmark cells {rep['dataset']}", "",
             f"{rep['features']:,} landmarks in {rep['cells']} cells, coverage {', '.join(rep['coverage'])}. "
             f"Largest cell {rep['largestCell']} ({rep['largestBytes'] / 1024:.0f} KiB).", "",
             f"Candidates per theme: {rep['candidates']}; merged duplicates: {rep['mergedDuplicates']}; "
             f"places dropped next to a theme twin: {rep['placesDroppedNearThemeTwin']}; "
             f"tower geometry snaps: {rep['snapped']}.", "",
             "Kinds: " + ", ".join(f"{k} {n}" for k, n in rep["kinds"].items()), "",
             f"Position uncertainty p: median {rep['p']['p50']} m, 90th percentile {rep['p']['p90']} m, "
             f"max {rep['p']['max']} m; {rep['p']['atLeast100m']} landmarks at 100 m or more.", ""]
    missing = [k for k in rep["knownLandmarks"] if not k["found"]]
    lines.append(f"Known landmarks: {len(rep['knownLandmarks']) - len(missing)}/{len(rep['knownLandmarks'])} found"
                 + ("." if not missing else ", missing: " + ", ".join(k["name"] for k in missing) + "."))
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--release", help="Overture release (default: latest in the STAC catalogue)")
    ap.add_argument("--countries", default=",".join(C.COVERAGE))
    ap.add_argument("--cells", help="restrict to these coverage cells, e.g. 52_9,52_10 (local test builds)")
    ap.add_argument("--out", default="public")
    ap.add_argument("--work", default="work")
    ap.add_argument("--memory", default=os.environ.get("AIME_DUCKDB_MEMORY", "4GB"))
    ap.add_argument("--threads", type=int, default=int(os.environ.get("AIME_DUCKDB_THREADS", "4")))
    args = ap.parse_args(argv)

    release = args.release or overture.latest_release()
    countries = tuple(args.countries.split(","))
    work = os.path.join(args.work, release)
    os.makedirs(work, exist_ok=True)
    log(f"release {release}, countries {','.join(countries)}")
    con = overture.connect(work, args.memory, args.threads)

    cov_file = os.path.join(work, f"coverage-{'-'.join(countries)}.json")
    if os.path.exists(cov_file):
        cells = {tuple(c) for c in json.load(open(cov_file))}
    else:
        cells = overture.coverage_cells(con, release, countries, union_box(countries))
        json.dump(sorted(cells), open(cov_file, "w"))
    if args.cells:
        wanted = parse_cells(args.cells)
        if not wanted <= cells:
            sys.exit(f"cells outside the coverage: {sorted(wanted - cells)}")
        cells = wanted
        work = os.path.join(work, "cells-" + "-".join(C.cell_name(*c) for c in sorted(cells)))
        os.makedirs(work, exist_ok=True)
    log(f"coverage: {len(cells)} cells")

    rows = overture.extract(con, release, overture.box_of(cells), work, log)
    features, stats = select(rows)
    grouped = group(features, cells)
    log(f"selected {stats['features']} features, {len(grouped)} non-empty cells")

    if os.path.exists(args.out):
        shutil.rmtree(args.out)
    built = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    index = write(args.out, release, built, grouped, countries)
    errs, summary = validate(args.out)
    if errs:
        for e in errs[:50]:
            print("ERROR", e)
        sys.exit(f"{len(errs)} contract error(s); nothing may be published.")
    known = check_known(grouped, cells)
    rep = report(stats, grouped, index, summary, known)
    with open(os.path.join(args.work, "report.json"), "w", encoding="utf-8") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=1)
    md = markdown(rep)
    with open(os.path.join(args.work, "report.md"), "w", encoding="utf-8") as fh:
        fh.write(md)
    print(md)
    log("valid; ready to publish")


if __name__ == "__main__":
    main()
