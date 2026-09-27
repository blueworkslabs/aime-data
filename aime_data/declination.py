"""Magnetic declination per cell (additive cell field `declination`).

WMM2025 (pygeomag, MIT) at the cell centre, sea level, degrees east of true
north, one decimal. The epoch is the Overture release date rather than the
build date, so an identical rebuild stays byte-identical. The Aimé module uses
it to turn the phone's magnetic compass hint into a true bearing without the
phone sending its position anywhere.
"""
import datetime
import functools

from .contract import CELL_DEG


@functools.lru_cache(maxsize=1)
def _model():
    from pygeomag import GeoMag
    return GeoMag(coefficients_file="wmm/WMM_2025.COF")


def decimal_year(release):
    """2026-09-23.1 → 2026.727 (the release date as a decimal year)."""
    day = datetime.date.fromisoformat(release.split(".")[0])
    start, end = datetime.date(day.year, 1, 1), datetime.date(day.year + 1, 1, 1)
    return day.year + (day - start).days / (end - start).days


def declination(lat, lon, release):
    """Declination at the centre of cell (lat, lon), degrees east, one decimal."""
    d = _model().calculate(glat=lat + CELL_DEG / 2, glon=lon + CELL_DEG / 2, alt=0,
                           time=decimal_year(release)).d
    return round(d, 1) + 0.0  # never -0.0
