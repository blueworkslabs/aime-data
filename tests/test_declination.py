import json
import os
import shutil
import tempfile
import unittest

from aime_data.cells import group, write
from aime_data.declination import decimal_year, declination
from aime_data.validate import read, validate

REL = "2026-09-23.1"


class Declination(unittest.TestCase):
    def test_decimal_year_is_the_release_date(self):
        self.assertAlmostEqual(decimal_year("2026-01-01.0"), 2026.0)
        self.assertAlmostEqual(decimal_year(REL), 2026 + 265 / 365)

    def test_wmm2025_at_cell_centres(self):
        # Germany/Austria are all a few degrees east in 2026 (WMM2025).
        self.assertEqual(declination(52, 9, REL), 4.1)   # Hannover cell, centre 52.5/9.5
        self.assertEqual(declination(47, 11, REL), 4.3)  # Innsbruck cell
        for lat, lon in ((46, 9), (54, 6), (48, 16), (55, 14)):
            self.assertTrue(2 <= declination(lat, lon, REL) <= 7, (lat, lon))
        self.assertEqual(declination(52, 9, REL), declination(52, 9, REL), "deterministic per release")

    def test_cells_carry_it_and_the_validator_checks_it(self):
        d = tempfile.mkdtemp()
        try:
            f = {"name": "Telemax", "kind": "communication_tower", "lat": 52.39306, "lon": 9.79971, "e": 282,
                 "wikidata": None, "w": 1.8, "p": 8}
            index = write(d, REL, "2026-09-27T12:00:00Z", group([f], {(52, 9)}))
            path = os.path.join(d, "v1", index["path"], "52_9.json")
            doc = json.loads(read(path))
            self.assertEqual(doc["declination"], 4.1)
            self.assertEqual(list(doc), ["schema", "release", "revision", "cell", "declination", "f"])
            self.assertEqual(validate(d)[0], [])
            for bad in (None, "4.1", 4.12, 200, float("nan")):
                with self.subTest(bad=bad):
                    with open(path, "w", encoding="utf-8") as fh:
                        fh.write(json.dumps(dict(doc, declination=bad)))
                    self.assertTrue(any("declination" in e for e in validate(d)[0]))
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(json.dumps({k: v for k, v in doc.items() if k != "declination"}))
            self.assertTrue(any("keys must be" in e for e in validate(d)[0]), "new builds always carry it")
        finally:
            shutil.rmtree(d)


if __name__ == "__main__":
    unittest.main()
