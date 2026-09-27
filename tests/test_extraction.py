import re
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from aime_data import overture as O

class FakeConnection:
    description = [('name',)]
    def __init__(self): self.copies = 0
    def execute(self, sql):
        if sql.startswith('COPY'):
            self.copies += 1
            Path(sql.split(" TO '")[1].split("'")[0]).write_text('fixture')
        return self
    def fetchall(self): return [('feature',)]

class Extraction(unittest.TestCase):
    def test_cache_is_bound_to_region_release_and_query(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(O, 'source', return_value='fixture'):
            con = FakeConnection()
            get = lambda rel, box: O.extract(con, rel, box, tmp, lambda _: None)
            get('2026-09-23.1', (9,46,17,50)); self.assertEqual(con.copies, 4)
            get('2026-09-23.1', (9,46,17,50)); self.assertEqual(con.copies, 4)
            get('2026-09-23.1', (5,46,17,56)); self.assertEqual(con.copies, 8)
            get('2026-10-23.1', (5,46,17,56)); self.assertEqual(con.copies, 12)
            with patch.object(O, 'CENTRE', O.CENTRE + ' '):
                get('2026-10-23.1', (5,46,17,56)); self.assertEqual(con.copies, 16)

    def test_sql_prefilter_includes_sharp_s_castle(self):
        sql = O.QUERIES['buildings'][2]
        pattern = re.search(r"regexp_matches\(names.primary, '([^']+)'", sql).group(1)
        for name in ['Schloß Herrenhausen', 'Schloss Herrenhausen', 'SCHLOẞ Herrenhausen']:
            self.assertIsNotNone(re.search(pattern, name, re.I), name)

if __name__ == '__main__': unittest.main()
