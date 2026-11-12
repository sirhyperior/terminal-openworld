"""Reusable diagnostic helpers reserve reports and retain startup failures."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import benchmark_same_geometry, verify_geometry


class WorkspaceDiagnosticTests(unittest.TestCase):
    def test_same_geometry_startup_failure_retains_reserved_report_and_prevents_overwrite(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            root = Path(directory)
            (root / 'ascii3d').mkdir()
            (root / 'ascii3d' / '__init__.py').write_text('')
            report = root / 'report.json'
            arguments = ['--before-source', str(root), '--save', str(report)]
            with patch.object(benchmark_same_geometry.pair, 'load_engine', side_effect=RuntimeError('fixture setup failure')), \
                    redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
                self.assertEqual(benchmark_same_geometry.main(arguments), 1)
            retained = report.read_bytes()
            saved = json.loads(retained)
            self.assertFalse(saved['complete'] or saved['passed'])
            self.assertEqual(saved['errors'][0]['phase'], 'startup')
            self.assertIn('fixture setup failure', saved['errors'][0]['message'])
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                benchmark_same_geometry.main(arguments)
            self.assertEqual(caught.exception.code, 2)
            self.assertEqual(report.read_bytes(), retained)

    def test_exact_geometry_startup_failure_retains_reserved_report_and_prevents_overwrite(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            root = Path(directory)
            (root / 'ascii3d').mkdir()
            (root / 'ascii3d' / '__init__.py').write_text('')
            report = root / 'report.json'
            arguments = ['--before-source', str(root), '--save', str(report), '--rays-per-scene', '0']
            with patch.object(verify_geometry, 'load_engine', side_effect=RuntimeError('fixture setup failure')), \
                    redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
                self.assertEqual(verify_geometry.main(arguments), 1)
            retained = report.read_bytes()
            saved = json.loads(retained)
            self.assertFalse(saved['complete'] or saved['passed'])
            self.assertEqual(saved['errors'][0]['phase'], 'startup')
            self.assertEqual(saved['pairs'], [])
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                verify_geometry.main(arguments)
            self.assertEqual(caught.exception.code, 2)
            self.assertEqual(report.read_bytes(), retained)


if __name__ == '__main__':
    unittest.main()
