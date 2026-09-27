import unittest

from aime_data import rules as R
from aime_data.contract import KINDS


def row(**kw):
    base = {"lat": 52.37, "lon": 9.73}
    base.update(kw)
    return base


class ThemeRules(unittest.TestCase):
    def test_land_needs_name_and_terrain_class(self):
        f = R.land(row(name="Benther Berg", cls="peak", elevation=173, wikidata="Q1"))
        self.assertEqual((f["kind"], f["e"], f["wikidata"]), ("peak", 173, "Q1"))
        self.assertIsNone(R.land(row(name=None, cls="peak")))
        self.assertIsNone(R.land(row(name="Wald", cls="forest")))

    def test_infra_classes_tags_and_masts(self):
        self.assertEqual(R.infra(row(name="Hochzeitsturm", cls="observation"))["kind"], "observation")
        self.assertEqual(R.infra(row(name="Annaturm", cls="viewpoint", man_made="tower"))["kind"], "tower")
        self.assertEqual(R.infra(row(name="Sender", cls="x", man_made="communications_tower"))["kind"],
                         "communication_tower")
        self.assertEqual(R.infra(row(name="Burgruine", cls="defensive", historic="ruins"))["kind"], "ruins")
        mast = R.infra(row(name=None, cls="mobile_phone_tower", height=62.0))
        self.assertEqual((mast["name"], mast["kind"], mast["e"]), ("Communication tower", "communication_tower", 62.0))
        self.assertIsNone(R.infra(row(name=None, cls="mobile_phone_tower", height=49.0)))
        self.assertIsNone(R.infra(row(name=None, cls="observation")), "unnamed class matches need a name")
        self.assertEqual(R.infra(row(name="Europabrücke", cls="bridge", wikidata="Q2"))["kind"], "bridge")
        self.assertIsNone(R.infra(row(name="Some bridge", cls="bridge")), "bridges need a Wikidata id")

    def test_buildings_classes_castle_names_and_tall(self):
        self.assertEqual(R.buildings(row(name="Marktkirche", cls="church", height=97))["kind"], "church")
        self.assertEqual(R.buildings(row(name="Schloss Marienburg", cls=None))["kind"], "castle")
        self.assertEqual(R.buildings(row(name="Marienburg", cls="yes"))["kind"], "castle")
        self.assertEqual(R.buildings(row(name="Kloster Loccum", cls=None))["kind"], "monastery")
        self.assertEqual(R.buildings(row(name="Festung Marienberg", cls=None))["kind"], "fort")
        tall = R.buildings(row(name=None, cls="office", height=120.0))
        self.assertEqual((tall["name"], tall["kind"]), ("Tall building", "tall_building"))
        self.assertIsNone(R.buildings(row(name="Rathaus", cls="civic", height=40)))
        self.assertIsNone(R.buildings(row(name="Chapel", cls=None)), "a religious class is required without a keyword")

    def test_castle_words_not_substrings(self):
        for name in ("Burger King", "Hamburger Hof", "Bahnhof Nienburg", "Amtsgericht Burgwedel",
                     "Alte Schlosserei", "Schlossstraße 12", "Burgmuseum", "Dr. Joachim Schlosser"):
            with self.subTest(name):
                self.assertIsNone(R.buildings(row(name=name, cls=None)))
        for name, kind in (("Burg Eltz", "castle"), ("Bodenengern Wasserschloss", "castle"),
                           ("Marienburg", "castle"), ("Asseburg (Ringwall)", "castle"),
                           ("Dachenhausenpalais", "castle"), ("Zisterzienserkloster Loccum", "monastery"),
                           ("Burg Rohden Burgruine", "castle"), ("Schloß Herrenhausen", "castle")):
            with self.subTest(name):
                self.assertEqual(R.buildings(row(name=name, cls=None))["kind"], kind)

    def test_historic_site_words(self):
        site = lambda name: R.places(row(name=name, category="historic_site", confidence=0.8))
        self.assertEqual(site("Burgruine Hohenstein")["kind"], "ruins")
        self.assertEqual(site("Bismarckturm")["kind"], "tower")
        self.assertIsNone(site("Altstadt Nienburg/Weser"))
        self.assertIsNone(site("Fortuna-Brunnen"))

    def test_bridges_need_a_bridge_name(self):
        bridge = lambda name: R.infra(row(name=name, cls="bridge", wikidata="Q98035117"))
        self.assertEqual(bridge("Europabrücke")["kind"], "bridge")
        self.assertEqual(bridge("Kochertalviadukt")["kind"], "bridge")
        self.assertIsNone(bridge("Bückeburger Allee"), "street names carried by a bridge are not landmarks")
        self.assertIsNone(bridge("Osterbrückenweg"))

    def test_places_confidence_and_keywords(self):
        self.assertEqual(R.places(row(name="Hermannsdenkmal", category="monument", confidence=0.9))["kind"], "monument")
        self.assertEqual(R.places(row(name="Gedenkstätte", category="memorial_site", confidence=0.6))["kind"], "memorial")
        self.assertIsNone(R.places(row(name="Denkmal", category="monument", confidence=0.59)))
        self.assertEqual(R.places(row(name="Ruine Hohenstein", category="historic_site", confidence=0.7))["kind"], "ruins")
        self.assertEqual(R.places(row(name="Bismarckwarte", category="historic_site", confidence=0.7))["kind"], "tower")
        self.assertIsNone(R.places(row(name="Alter Friedhof", category="historic_site", confidence=0.9)))
        self.assertIsNone(R.places(row(name="HSV Arena", category="stadium_arena", confidence=0.99)))
        self.assertIsNone(R.places(row(name="Kirche", category="christian_place_of_worship", confidence=0.69)))
        self.assertIsNone(R.places(row(name="Berg - Wanderweg", category="mountain", confidence=0.9)))
        self.assertIsNone(R.places(row(name="Deister", category="mountain", confidence=0.79)))

    def test_names_are_nfc_trimmed_and_capped(self):
        decomposed = "Marienkirche Lübeck"
        self.assertEqual(R.clean_name(decomposed), "Marienkirche Lübeck")
        self.assertEqual(R.clean_name("  Dom \n St.  Jakob "), "Dom St. Jakob")
        self.assertEqual(len(R.clean_name("x" * 200)), 80)
        self.assertIsNone(R.clean_name("   "))

    def test_every_kind_is_in_the_contract(self):
        kinds = {k for _, k in R.WORD_KINDS} | set(R.INFRA_CLASSES) | set(R.MAN_MADE.values()) | \
            set(R.HISTORIC.values()) | set(R.BUILDING_CLASSES) | set(R.PLACES_KINDS.values()) | \
            {"peak", "hill", "volcano", "bridge", "communication_tower", "tall_building", "church"}
        self.assertLessEqual(kinds, set(KINDS))


class CrossThemeRules(unittest.TestCase):
    def test_places_church_only_without_buildings_church_nearby(self):
        rows = {
            "buildings": [row(name="St. Marien", cls="church", lat=52.0, lon=9.0)],
            "places": [row(name="Pfarrei St. Marien", category="christian_place_of_worship", confidence=0.95,
                           lat=52.001, lon=9.0),
                       row(name="Aegidienkirche", category="christian_place_of_worship", confidence=0.99,
                           lat=52.3706, lon=9.7392)],
        }
        feats, stats = R.select(rows)
        self.assertEqual(sorted(f["name"] for f in feats), ["Aegidienkirche", "St. Marien"])
        self.assertEqual(stats["places_dropped_near_theme_twin"]["places:church"], 1)

    def test_places_mountain_only_without_land_peak_of_that_name(self):
        rows = {
            "land": [row(name="Gehrdener Berg", cls="hill", lat=52.30, lon=9.59)],
            "places": [row(name="Gehrdener Berg", category="mountain", confidence=0.86, lat=52.31, lon=9.59),
                       row(name="Süllberg", category="mountain", confidence=0.9, lat=52.28, lon=9.55)],
        }
        feats, stats = R.select(rows)
        self.assertEqual(sorted((f["name"], f["kind"]) for f in feats),
                         [("Gehrdener Berg", "hill"), ("Süllberg", "peak")])
        self.assertEqual(stats["places_dropped_near_theme_twin"]["places:mountain"], 1)

    def test_dedupe_keeps_provenance_order_and_fills_gaps(self):
        rows = {
            "infra": [row(name="Burgbergturm", cls="observation", height=None, wikidata=None, lat=52.3146, lon=9.5856)],
            "buildings": [row(name="Burgberg-Turm", cls="tower", height=31, lat=52.3147, lon=9.5857)],
            "places": [row(name="Burgbergturm", category="historic_site", confidence=0.8, lat=52.3150, lon=9.5860),
                       row(name="Burgbergturm", category="historic_site", confidence=0.8, lat=52.33, lon=9.5856)],
        }
        feats, stats = R.select(rows)
        self.assertEqual(len(feats), 3, "Burgberg-Turm normalises differently; the far one is 1.7 km away")
        first = next(f for f in feats if f["name"] == "Burgbergturm" and f["src"] == "infra")
        self.assertEqual(first["kind"], "observation")
        self.assertEqual(stats["merged"], 1)

        rows = {"land": [row(name="Großer Feldberg", cls="peak", elevation=None, wikidata=None, lat=50.2318, lon=8.4568)],
                "places": [row(name="Grosser Feldberg", category="historic_site", confidence=0.9, lat=50.232, lon=8.457)]}
        feats, _ = R.select(rows)
        self.assertEqual(len(feats), 1, "ASCII-folded names merge")

    def test_dedupe_fills_elevation_and_wikidata(self):
        rows = {"infra": [row(name="Telemax", cls="communication_tower", height=None, wikidata=None)],
                "buildings": [row(name="Telemax", cls="tower", height=282.0)]}
        feats, _ = R.select(rows)
        self.assertEqual(len(feats), 1)
        self.assertEqual((feats[0]["kind"], feats[0]["e"]), ("communication_tower", 282.0))
        self.assertEqual(feats[0]["w"], 1.8)  # 1.3 × 1.4

    def test_output_is_deterministic(self):
        rows = {"land": [row(name=n, cls="peak", elevation=100, lat=47 + i / 100, lon=11) for i, n in enumerate("CAB")]}
        a, _ = R.select(rows)
        rows["land"].reverse()
        b, _ = R.select(rows)
        self.assertEqual([R.record(f) for f in a], [R.record(f) for f in b])


class PositionUncertainty(unittest.TestCase):
    """p = clamp(max(floor(source), 0.5 × half-diagonal), 5, 1000), rounded up."""

    def test_floors_by_source(self):
        rows = {
            "land": [row(name="Benther Berg", cls="peak", elevation=173, lat=52.3386, lon=9.6166)],
            "infra": [row(name="Telemax", cls="communication_tower", height=282, lat=52.393, lon=9.800)],
            "buildings": [row(name="Marktkirche", cls="church", lat=52.3718, lon=9.7353)],
            "places": [row(name="Aegidienkirche", category="christian_place_of_worship", confidence=0.99,
                           lat=52.3706, lon=9.7392),
                       row(name="Denkmal am Berg", category="monument", confidence=0.9, lat=52.30, lon=9.50),
                       row(name="Gehrdener Berg", category="mountain", confidence=0.86, lat=52.303, lon=9.589)],
        }
        p = {f["name"]: f["p"] for f in R.select(rows)[0]}
        self.assertEqual(p, {"Benther Berg": 8, "Telemax": 8, "Marktkirche": 10, "Aegidienkirche": 60,
                             "Denkmal am Berg": 60, "Gehrdener Berg": 250})

    def test_footprints_widen_p(self):
        # 60 × 25 m church: half-diagonal 32.5 m → p 17 (> the 10 m floor)
        church = R.buildings(row(name="Marktkirche", cls="church", lat=52.0, dx=60 / (111195 * 0.6157), dy=25 / 111195))
        self.assertEqual(church["p"], 17)
        # 300 × 200 m castle: half-diagonal 180 m → p 91
        castle = R.buildings(row(name="Schloss Groß", cls="castle", lat=52.0, dx=300 / (111195 * 0.6157), dy=200 / 111195))
        self.assertEqual(castle["p"], 91)
        # 500 m bridge (a line): half-diagonal 250 m → p 125 against the 8 m floor
        bridge = R.infra(row(name="Talbrücke", cls="bridge", wikidata="Q1", lat=52.0, dx=500 / (111195 * 0.6157), dy=0))
        self.assertEqual(bridge["p"], 125)

    def test_clamped(self):
        huge = R.buildings(row(name="Burg X", cls="castle", lat=52.0, dx=0.1, dy=0.1))
        self.assertEqual(huge["p"], 1000)
        point = R.land(row(name="Gipfel", cls="peak", dx=0, dy=0))
        self.assertEqual(point["p"], 8)
        self.assertEqual(R.uncertainty("land", row(dx=None, dy=None)), 8)

    def test_merge_keeps_the_primary_p(self):
        rows = {"infra": [row(name="Telemax", cls="communication_tower", height=None, lat=52.393, lon=9.800)],
                "buildings": [row(name="Telemax", cls="tower", height=282.0, lat=52.393, lon=9.800,
                                  dx=0.001, dy=0.001)]}
        feats, _ = R.select(rows)
        self.assertEqual((len(feats), feats[0]["src"], feats[0]["p"]), (1, "infra", 8))
        rows = {"land": [row(name="Kaliberg", cls="peak", lat=52.3127, lon=9.6476)],
                "places": [row(name="Kaliberg", category="castle", confidence=0.9, lat=52.3128, lon=9.6477)]}
        feats, _ = R.select(rows)
        self.assertEqual([f["p"] for f in feats], [8])


class Weights(unittest.TestCase):
    def w(self, kind, e=None, wikidata=None):
        return R.weight({"kind": kind, "e": e, "wikidata": wikidata})

    def test_table(self):
        self.assertEqual(self.w("peak", 880), 1.5)
        self.assertEqual(self.w("peak", 880, "Q1"), 1.8)
        self.assertEqual(self.w("peak"), 1.2)
        self.assertEqual(self.w("hill", 300), 1.2, "no size bonus for terrain")
        self.assertEqual(self.w("cathedral", 40, "Q1"), 1.6)
        self.assertEqual(self.w("communication_tower", 338, "Q1"), 2.0, "1.3 × 1.2 × 1.4 clamps to 2.0")
        self.assertEqual(self.w("church", 97), 1.3)
        self.assertEqual(self.w("chapel"), 0.6)
        self.assertEqual(self.w("chapel", 10, "Q1"), 0.7)
        self.assertEqual(self.w("monument"), 1.0)
        self.assertEqual(self.w("tower", 50), 1.3)

    def test_record_shape(self):
        f = {"name": "Europaturm", "kind": "communication_tower", "lat": 50.135321, "lon": 8.654634,
             "e": 337.6, "wikidata": "Q1", "w": 2.0}
        f["p"] = 8
        self.assertEqual(R.record(f), ["Europaturm", "communication_tower", 50.13532, 8.65463, 338, 2.0, 8])
        self.assertEqual(R.record(dict(f, e=None))[4], 0)


if __name__ == "__main__":
    unittest.main()
