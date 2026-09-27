"""Known landmarks from the spike and the Hannover test region. The build
reports which are present; a missing one is a warning for review, not a
failure, because Overture data changes between releases."""
import math

from .rules import metres, norm

# (name fragment, lat, lon). Found when a record within 1.5 km contains the
# normalised fragment in its normalised name.
KNOWN = (
    # Rhine-Main
    ("Großer Feldberg", 50.2318, 8.4568), ("Europaturm", 50.1353, 8.6546),
    ("Bartholomäus", 50.1107, 8.6853), ("Dom St. Martin", 49.9990, 8.2739),
    ("Hochzeitsturm", 49.8771, 8.6673), ("Commerzbank Tower", 50.1112, 8.6744),
    ("Messeturm", 50.1124, 8.6527), ("Main Tower", 50.1125, 8.6722),
    # Innsbruck
    ("Hafelekarspitze", 47.3128, 11.3863), ("Patscherkofel", 47.2088, 11.4606),
    ("Serles", 47.1240, 11.3814), ("Frau Hitt", 47.3052, 11.3505),
    ("St. Jakob", 47.2694, 11.3942), ("Stadtturm", 47.2682, 11.3935),
    ("Bergisel", 47.2468, 11.4001), ("Europabrücke", 47.2022, 11.4019),
    # Hannover (hardware test region)
    ("Telemax", 52.3931, 9.7997), ("Neues Rathaus", 52.3672, 9.7374),
    ("Marktkirche", 52.3718, 9.7353), ("Annaturm", 52.2467, 9.5088),
    ("Nordmannsturm", 52.2699, 9.4534), ("Benther Berg", 52.3386, 9.6166),
    ("Kaliberg", 52.3127, 9.6476), ("Burgbergturm", 52.3146, 9.5856),
    ("Aegidienkirche", 52.3706, 9.7392), ("Marienburg", 52.1737, 9.7701),
    ("Herrenhausen", 52.3906, 9.6989), ("Gehrdener Berg", 52.3029, 9.5890),
    ("Rathausturm", 52.3672, 9.7373), ("Heizkraftwerk Linden", 52.3731, 9.7143),
    # Surveyed tower, not the geocoded places point 135 m west (RADIUS_M allows either,
    # so the test in tests/test_tower_geometry.py checks the snap itself).
    ("VW Tower", 52.3801, 9.7431),
)
RADIUS_M = 1500


def check_known(grouped, cells):
    """[{name, cell, found, match}] for known landmarks inside the built cells."""
    out = []
    for name, lat, lon in KNOWN:
        cell = (math.floor(lat), math.floor(lon))
        if cell not in cells:
            continue
        key, here = norm(name), {"lat": lat, "lon": lon}
        match = next((r for r in grouped.get(cell, ())
                      if key in norm(r[0]) and metres(here, {"lat": r[2], "lon": r[3]}) < RADIUS_M), None)
        out.append({"name": name, "cell": f"{cell[0]}_{cell[1]}", "found": bool(match),
                    "match": match[:2] if match else None})
    return out
