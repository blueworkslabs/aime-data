"""Exercise publication against a disposable local bare remote, never GitHub."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from aime_data.cells import write

ROOT = Path(__file__).resolve().parents[1]


class Publication(unittest.TestCase):
    def test_revisions_retention_immutability_and_failed_remote(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            remote, repo = root / 'remote.git', root / 'repo'

            def run(*args, cwd=repo, check=True):
                return subprocess.run(args, cwd=cwd, check=check, capture_output=True, text=True)
            run('git', 'init', '--bare', str(remote), cwd=root)
            run('git', 'init', str(repo), cwd=root)
            run('git', 'remote', 'add', 'origin', str(remote))
            env = dict(os.environ, PYTHONPATH=str(ROOT))
            public = repo / 'public'

            def publish(release, name='Tower', success=True, built='2026-09-27T08:00:00Z'):
                if public.exists():
                    shutil.rmtree(public)
                write(str(public), release, built, {(52, 9): [[name, 'tower', 52.5, 9.5, 0, 1.0, 8]]})
                result = subprocess.run(['bash', str(ROOT / 'scripts/publish.sh'), str(public)], cwd=repo, env=env,
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
                return result.stdout

            def head(): return run('git', '--git-dir=' + str(remote), 'rev-parse', 'pages').stdout.strip()
            def files(): return run('git', '--git-dir=' + str(remote), 'ls-tree', '-r', '--name-only', 'pages').stdout
            def show(path): return run('git', '--git-dir=' + str(remote), 'show', 'pages:' + path).stdout
            def index(): return json.loads(show('v1/index.json'))

            a, b, c = '2026-07-23.1', '2026-08-23.1', '2026-09-23.1'
            publish(a)
            publish(b)
            self.assertEqual(index()['dataset'], b + '-r1')
            self.assertIn(a + '-r1/cells/', files())
            b1 = show(f'v1/{b}-r1/cells/52_9.json')

            before = head()
            self.assertIn('unchanged', publish(b, built='2026-09-28T08:00:00Z'))
            self.assertEqual(head(), before, 'an identical rebuild is a no-op, whatever its build time')

            publish(b, 'Changed tower')
            self.assertEqual((index()['dataset'], index()['revision']), (b + '-r2', 2))
            self.assertEqual(json.loads(show(f'v1/{b}-r2/cells/52_9.json'))['revision'], 2)
            self.assertEqual(show(f'v1/{b}-r1/cells/52_9.json'), b1, 'a published dataset is never rewritten')
            self.assertNotIn(a + '-r1/cells/', files(), 'only the current and previous dataset are kept')

            publish(c)
            self.assertEqual(index()['dataset'], c + '-r1')
            self.assertIn(b + '-r2/cells/', files())
            self.assertNotIn(b + '-r1/cells/', files())

            before = head()
            publish(b, success=False)
            self.assertEqual(head(), before, 'an older release is never published over a newer one')
            run('git', 'remote', 'set-url', 'origin', str(root / 'missing.git'))
            publish('2026-10-23.1', success=False)
            self.assertEqual(head(), before)


if __name__ == '__main__':
    unittest.main()
