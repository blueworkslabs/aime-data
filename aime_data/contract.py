"""Data contract, schema 1 (README.md). The Aimé module relies on these values."""

SCHEMA = 1
CELL_DEG = 1
MAX_CELL_BYTES = 1024 * 1024  # build fails at or above this; the host caps JSON at 2 MiB
NAME_MAX = 80
W_MIN, W_MAX = 0.5, 2.0
LICENSE = "ODbL-1.0"
ATTRIBUTION = "© OpenStreetMap contributors, Overture Maps Foundation"
COVERAGE = ("DE", "AT")
# Generous boxes around each country, for STAC file selection only (x0, y0, x1, y1).
COUNTRY_BOXES = {"DE": (5.5, 47.0, 15.5, 55.5), "AT": (9.3, 46.2, 17.4, 49.2)}

TERRAIN = ("peak", "hill", "volcano")
# Allowed kinds (validation and labels only; position uncertainty is per feature).
KINDS = sorted(TERRAIN + (
    "tower", "observation", "communication_tower", "mast", "bell_tower", "water_tower",
    "watchtower", "minaret", "lighthouse", "windmill", "chimney", "radar",
    "church", "cathedral", "chapel", "mosque", "synagogue", "temple", "monastery",
    "castle", "ruins", "fort", "tall_building", "gasometer", "cooling",
    "monument", "memorial", "bridge", "dam",
))
P_MIN, P_MAX = 5, 1000  # per-feature position uncertainty p, metres

HEADERS = """/v1/index.json
  Cache-Control: public, max-age=3600
  Access-Control-Allow-Origin: *
/v1/*/cells/*
  Cache-Control: public, max-age=31536000, immutable
  Access-Control-Allow-Origin: *
"""


def cell_name(lat, lon):
    """Integer south-west corner, e.g. 50_8, 47_-1, -34_18."""
    return f"{lat}_{lon}"


def dataset_name(release, revision):
    """Published dataset directory, e.g. 2026-09-23.1-r1."""
    return f"{release}-r{revision}"
