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
STRUCTURE_POINTS = (
    "tower", "observation", "communication_tower", "mast", "bell_tower", "water_tower",
    "watchtower", "minaret", "lighthouse", "windmill", "chimney", "radar",
)
BUILDING_CENTROIDS = (
    "church", "cathedral", "chapel", "mosque", "synagogue", "temple", "monastery",
    "castle", "ruins", "fort", "tall_building", "gasometer", "cooling",
)
PLACES_POINTS = ("monument", "memorial")
LARGE_STRUCTURES = ("bridge", "dam")

KINDS = {
    **{k: {"placementM": 8} for k in TERRAIN + STRUCTURE_POINTS},
    **{k: {"placementM": 25} for k in BUILDING_CENTROIDS},
    **{k: {"placementM": 30} for k in PLACES_POINTS},
    **{k: {"placementM": 50} for k in LARGE_STRUCTURES},
}

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
