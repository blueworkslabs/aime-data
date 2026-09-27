"""Exercise publication against a disposable local bare remote, never GitHub."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from aime_data.cells import write

ROOT = Path(__file__).resolve().parents[1]

class Publication(unittest.TestCase):
    def test_retention_immutability_and_failed_remote(self):
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
            def publish(release, name='Tower', success=True):
                if public.exists(): shutil.rmtree(public)
                write(str(public), release, '2026-09-27T08:00:00Z', {(52, 9): [[name, 'tower', 52.5, 9.5, 0, 1.0]]})
                result = subprocess.run(['bash', str(ROOT / 'scripts/publish.sh'), str(public)], cwd=repo, env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
            def head(): return run('git', '--git-dir=' + str(remote), 'rev-parse', 'pages').stdout.strip()
            def files(): return run('git', '--git-dir=' + str(remote), 'ls-tree', '-r', '--name-only', 'pages').stdout
            a,b,c = '2026-07-23.1','2026-08-23.1','2026-09-23.1'
            publish(a); publish(b)
            before=head()
            publish(b)
            self.assertEqual(head(), before)
            self.assertIn(a + '/cells/', files())
            publish(b, 'Changed tower', False)
            self.assertEqual(head(), before)
            publish(c)
            self.assertNotIn(a + '/cells/', files())
            self.assertIn(b + '/cells/', files())
            publish(b, success=False)
            before=head()
            run('git', 'remote', 'set-url', 'origin', str(root / 'missing.git'))
            publish('2026-10-23.1', success=False)
            self.assertEqual(head(), before)

if __name__ == '__main__': unittest.main()
