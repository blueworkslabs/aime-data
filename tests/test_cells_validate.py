import json
import os
import shutil
import tempfile
import unittest

from aime_data import contract as C
from aime_data.cells import group, write
from aime_data.landmarks import check_known
from aime_data.validate import read, validate

REL = "2026-09-23.1"
BUILT = "2026-09-27T12:00:00Z"


def put(path, data):
    binary = isinstance(data, bytes)
    with open(path, "wb" if binary else "w", **({} if binary else {"encoding": "utf-8"})) as fh:
        fh.write(data)


def feat(name, kind, lat, lon, e=None, w=1.0):
    return {"name": name, "kind": kind, "lat": lat, "lon": lon, "e": e, "wikidata": None, "w": w}


FEATURES = [
    feat("Telemax", "communication_tower", 52.393061, 9.799714, 282, 1.8),
    feat("Marktkirche", "church", 52.37179, 9.73533, 97, 1.3),
    feat("Aegidienkirche", "church", 52.3706, 9.7392, None, 1.1),
    feat("Benther Berg", "peak", 52.3386, 9.61661, 173, 1.8),
    feat("Edge", "tower", 52.999999, 9.5, 20, 1.0),  # rounds to 53.00000: next cell north
    feat("Zürich", "church", 47.37, 8.54, None, 1.1),  # outside the coverage cells
]
COVER = {(52, 9), (53, 9), (-34, 18), (47, -1)}


class Build(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.grouped = group(FEATURES, COVER)
        self.index = write(self.dir, REL, BUILT, self.grouped)

    def tearDown(self):
        shutil.rmtree(self.dir)

    def cell(self, name):
        return os.path.join(self.dir, "v1", REL, "cells", name + ".json")

    def test_layout_index_and_sorting(self):
        self.assertEqual(self.index["cells"], ["52_9", "53_9"])
        self.assertEqual(self.index["path"], f"{REL}/cells/")
        self.assertEqual(self.index["kinds"]["peak"], {"placementM": 8})
        self.assertEqual(self.index["kinds"]["church"], {"placementM": 25})
        self.assertEqual(self.index["kinds"]["memorial"], {"placementM": 30})
        self.assertEqual(self.index["kinds"]["dam"], {"placementM": 50})
        doc = json.loads(read(self.cell("52_9")))
        self.assertEqual((doc["schema"], doc["release"], doc["cell"]), (1, REL, [52, 9]))
        self.assertEqual([r[0] for r in doc["f"]], ["Benther Berg", "Telemax", "Marktkirche", "Aegidienkirche"])
        self.assertEqual(json.loads(read(self.cell("53_9")))["f"][0][2], 53.0)
        self.assertEqual(read(os.path.join(self.dir, "_headers")), C.HEADERS)
        self.assertIn(C.ATTRIBUTION, read(os.path.join(self.dir, "index.html")))
        errs, summary = validate(self.dir)
        self.assertEqual(errs, [])
        self.assertEqual((summary["cells"], summary["features"]), (2, 5))

    def test_negative_cell_names(self):
        d = tempfile.mkdtemp()
        try:
            idx = write(d, REL, BUILT, group([feat("Lion's Head", "peak", -33.93, 18.39, 669, 1.5),
                                                feat("West", "tower", 47.5, -0.5)], COVER))
            self.assertEqual(sorted(idx["cells"]), ["-34_18", "47_-1"])
            self.assertEqual(validate(d)[0], [])
        finally:
            shutil.rmtree(d)

    def rewrite(self, name, fn):
        path = self.cell(name)
        doc = json.loads(read(path))
        fn(doc)
        put(path, json.dumps(doc, ensure_ascii=False))

    def assertInvalid(self, fragment):
        errs, _ = validate(self.dir)
        self.assertTrue(any(fragment in e for e in errs), errs)

    def test_rejects_release_mismatch(self):
        self.rewrite("52_9", lambda d: d.update(release="2026-08-19.0"))
        self.assertInvalid("does not match the index")

    def test_rejects_unknown_kind_bounds_precision_weight(self):
        cases = [
            (lambda d: d["f"][0].__setitem__(1, "viewpoint"), "unknown kind"),
            (lambda d: d["f"][0].__setitem__(2, 53.2), "outside the cell"),
            (lambda d: d["f"][0].__setitem__(3, 9.123456), "more than 5 decimals"),
            (lambda d: d["f"][0].__setitem__(5, 2.4), "weight"),
            (lambda d: d["f"][0].__setitem__(4, 12.5), "e is not an integer"),
            (lambda d: d["f"][0].__setitem__(0, ""), "empty name"),
            (lambda d: d["f"][0].__setitem__(0, "Lübeck"), "not NFC"),
            (lambda d: d["f"].append(["x", "peak", 52.5, 9.5, 0]), "6-element"),
            (lambda d: d["f"].reverse(), "not sorted"),
            (lambda d: d.update(schema=2), "schema"),
        ]
        original = read(self.cell("52_9"), "rb")
        for fn, fragment in cases:
            with self.subTest(fragment):
                put(self.cell("52_9"), original)
                self.rewrite("52_9", fn)
                self.assertInvalid(fragment)

    def test_rejects_set_mismatch_and_size(self):
        os.remove(self.cell("53_9"))
        self.assertInvalid("listed in the index but missing")
        put(self.cell("53_9"), "{}")
        put(self.cell("40_1"), "{}")
        self.assertInvalid("file present but not in the index")
        big = [["x" * 70, "peak", 52.5, 9.5, 0, 1.0]] * 14000
        self.rewrite("52_9", lambda d: d.update(f=big))
        self.assertInvalid("bytes, limit")

    def test_write_refuses_oversized_cell(self):
        big = {(52, 9): [["x" * 70, "peak", 52.5, 9.5, 0, 1.0]] * 14000}
        d = tempfile.mkdtemp()
        try:
            with self.assertRaises(ValueError):
                write(d, REL, BUILT, big)
        finally:
            shutil.rmtree(d)

    def test_rejects_index_changes(self):
        path = os.path.join(self.dir, "v1", "index.json")
        index = json.loads(read(path))
        for key, value, fragment in [("kinds", {"peak": {"placementM": 8}}, "kinds differ"),
                                     ("path", "x/", "path"), ("attribution", "OSM", "attribution"),
                                     ("built", "yesterday", "built")]:
            with self.subTest(key):
                put(path, json.dumps(dict(index, **{key: value}), ensure_ascii=False))
                self.assertInvalid(fragment)

    def test_known_landmarks(self):
        known = {k["name"]: k["found"] for k in check_known(self.grouped, COVER)}
        self.assertTrue(known["Telemax"])
        self.assertTrue(known["Aegidienkirche"])
        self.assertFalse(known["Herrenhausen"])
        self.assertNotIn("Europaturm", known, "cells outside the build are not reported")


if __name__ == "__main__":
    unittest.main()
