import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from tracebench import analyze, percentile, route_key, render_markdown


def entry(time=100, status=200, url='https://example.test/users/42?token=secret'):
    return {'time': time, 'response': {'status': status}, 'request': {'method': 'GET', 'url': url}}


class AnalysisTests(unittest.TestCase):
    def test_percentiles_use_nearest_rank(self):
        self.assertEqual(percentile(list(range(1, 101)), .95), 95)
        self.assertEqual(percentile([10], .5), 10)

    def test_groups_ids_and_redacts_query(self):
        report = analyze({'log': {'entries': [entry(), entry(900, 503, 'https://example.test/users/99')]}})
        self.assertEqual(len(report['routes']), 1)
        self.assertEqual(report['routes'][0]['p95_ms'], 900)
        self.assertEqual(report['routes'][0]['error_rate'], .5)
        self.assertNotIn('secret', json.dumps(report))

    def test_uuid_normalization(self):
        self.assertEqual(route_key('https://x.test/a/123e4567-e89b-12d3-a456-426614174000'), '/a/:id')

    def test_invalid_entries_are_visible(self):
        report = analyze({'log': {'entries': [entry(-1), entry(float('nan')), {}, entry(True), entry(status=0)]}})
        self.assertEqual(report['skipped'], 4)
        self.assertEqual(report['routes'][0]['error_rate'], 1)

    def test_markdown_escapes_route(self):
        result = render_markdown(analyze({'log': {'entries': [entry(url='https://x.test/<tag>|x')]}}))
        self.assertIn('&lt;tag&gt;&#124;x', result)

    def test_bad_structure(self):
        with self.assertRaises(ValueError):
            analyze({})

    def test_cli_budget_and_invalid_capture(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'capture.har'
            path.write_text(json.dumps({'log': {'entries': [entry(500)]}}))
            run = subprocess.run([sys.executable, 'tracebench.py', str(path), '--max-p95', '100'], capture_output=True)
            self.assertEqual(run.returncode, 1)
            path.write_text('{')
            run = subprocess.run([sys.executable, 'tracebench.py', str(path)], capture_output=True)
            self.assertEqual(run.returncode, 2)


if __name__ == '__main__':
    unittest.main()
