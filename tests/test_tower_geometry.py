import unittest

from aime_data import rules as R

M = 1 / 111195  # one metre of latitude in degrees


def row(**kw):
    base = {"lat": 52.37, "lon": 9.73, "dx": 0, "dy": 0}
    base.update(kw)
    return base


class TowerGeometry(unittest.TestCase):
    def test_building_snaps_to_the_tower_inside_it(self):
        # Neues Rathaus: a 140 × 96 m footprint (p 43) with the dome point Rathausturm inside.
        rows = {
            "buildings": [row(name="Neues Rathaus", cls="government", height=97.7, lat=52.36724, lon=9.73736,
                              dx=0.00204, dy=0.00087)],
            "infra": [row(name="Rathausturm", cls="observation", man_made="tower", height=90.0,
                          lat=52.367243, lon=9.737341, dx=0.00008, dy=0.00006),
                      row(name=None, cls="bell_tower", height=None, lat=52.3669, lon=9.7366)],  # outside the bbox
        }
        feats, stats = R.select(rows)
        hall = next(f for f in feats if f["name"] == "Neues Rathaus")
        self.assertEqual((hall["lat"], hall["lon"], hall["snapped"]), (52.367243, 9.737341, "building-tower"))
        self.assertLess(hall["p"], 43)
        self.assertEqual(hall["p"], next(f for f in feats if f["name"] == "Rathausturm")["p"])
        self.assertEqual(stats["snapped"]["building-tower"], 1)

    def test_tallest_tower_wins_and_points_outside_are_ignored(self):
        church = row(name="St. Marien", cls="church", lat=52.0, lon=9.0, dx=60 * M / 0.6157, dy=30 * M)
        rows = {"buildings": [church],
                "infra": [row(cls="bell_tower", height=40, lat=52.0 + 10 * M, lon=9.0),
                          row(cls="bell_tower", height=55, lat=52.0 - 10 * M, lon=9.0),
                          row(cls="bell_tower", height=90, lat=52.0 + 40 * M, lon=9.0)]}
        f = R.select(rows)[0][0]
        self.assertAlmostEqual(f["lat"], 52.0 - 10 * M)
        self.assertEqual(f["e"], 55)

    def test_proximity_alone_never_relocates(self):
        # VW Tower (Telemoritz) and Hochhaus Lister Tor are different buildings 137 m apart.
        rows = {
            "places": [row(name="VW Tower", category="historic_site", confidence=0.87, lat=52.37992, lon=9.74118)],
            "buildings": [row(name="Hochhaus Lister Tor", cls="office", height=91.0, lat=52.38007, lon=9.74315,
                              dx=0.0006, dy=0.0003)],
            "infra": [row(name="Funkmast", cls="communication_tower", height=60, lat=52.38008, lon=9.74316)],
        }
        feats, stats = R.select(rows)
        vw = next(f for f in feats if f["name"] == "VW Tower")
        self.assertEqual((vw["lat"], vw["lon"], vw["p"]), (52.37992, 9.74118, 60))
        self.assertNotIn("snapped", vw)
        tall = next(f for f in feats if f["name"] == "Hochhaus Lister Tor")
        self.assertNotIn("snapped", tall, "an unrelated named mast on the roof is not the building's tower")
        self.assertEqual(stats["snapped"], {"building-tower": 0})

    def test_unnamed_point_needs_a_part_of_relation(self):
        church = row(name="St. Marien", cls="church", lat=52.0, lon=9.0, dx=60 * M / 0.6157, dy=30 * M)
        rows = {"buildings": [church, row(name="Kaufhaus", cls="tall_building", height=85, lat=52.1, lon=9.1,
                                          dx=0.001, dy=0.001)],
                "infra": [row(cls="observation", height=30, lat=52.0, lon=9.0),      # not a bell tower
                          row(cls="bell_tower", height=20, lat=52.1, lon=9.1)]}      # a bell tower, but not a church
        feats, _ = R.select(rows)
        self.assertTrue(all("snapped" not in f for f in feats))

    def test_power_plants_and_tall_stacks(self):
        rows = {
            "places": [row(name="Heizkraftwerk Linden", category="campus_building", confidence=0.76,
                           lat=52.3729, lon=9.7142),
                       row(name="Kanzlei Kraftwerk", category="professional_service", confidence=0.9),
                       row(name="Kraftwerk Stöcken", category="electric_utility_provider", confidence=0.6)],
            "infra": [row(name=None, cls="chimney", man_made="chimney", height=125.0, lat=52.3733, lon=9.7144),
                      row(name=None, cls="cooling", man_made="cooling_tower", height=95.0, lat=52.30, lon=9.60),
                      row(name=None, cls="chimney", man_made="chimney", height=60.0, lat=52.31, lon=9.61)],
        }
        feats, _ = R.select(rows)
        got = sorted((f["name"], f["kind"], f["src"]) for f in feats)
        self.assertEqual(got, [("Chimney · Heizkraftwerk Linden", "chimney", "infra"),
                               ("Cooling tower", "cooling", "infra"),
                               ("Heizkraftwerk Linden", "chimney", "places")],
                         "a stack within 300 m names its plant but keeps its own position; the plant stays "
                         "a separate places entry; offices, low-confidence plants and stacks below 80 m stay out")

    def test_plant_without_a_stack_is_a_places_chimney(self):
        rows = {"places": [row(name="Heizkraftwerk Linden", category="campus_building", confidence=0.76)]}
        f = R.select(rows)[0][0]
        self.assertEqual((f["kind"], f["p"]), ("chimney", 60))


if __name__ == "__main__":
    unittest.main()
