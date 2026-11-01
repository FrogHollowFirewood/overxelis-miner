"""Offline tests for benchmark evidence identity, accounting and aggregation."""
from pathlib import Path
import importlib.util
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('benchmark_native', ROOT / 'tools/benchmark_native.py')
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


class BenchmarkAccounting(unittest.TestCase):
    def test_elapsed_uses_monotonic_read_midpoints(self):
        class Engine:
            counts = iter((100, 210))
            def count(self): return next(self.counts)
        ticks = iter((0, 2_000_000, 1_100_000_000, 1_102_000_000))
        sleeps = []
        result = bench.sample(Engine(), 1, lambda: next(ticks), sleeps.append)
        self.assertEqual(sleeps, [1])
        self.assertEqual(result['completed_hashes'], 110)
        self.assertAlmostEqual(result['elapsed_seconds'], 1.1)
        self.assertAlmostEqual(result['hashes_per_second'], 100)
        self.assertEqual(result['counter_read_seconds'], [.002, .002])

    def test_backward_counter_refused(self):
        class Engine:
            counts = iter((12, 11))
            def count(self): return next(self.counts)
        ticks = iter((0, 1, 2, 3))
        with self.assertRaisesRegex(RuntimeError, 'Invalid native counter'):
            bench.sample(Engine(), 1, lambda: next(ticks), lambda _: None)

    def test_pairing_ignores_order_and_incomplete_trial(self):
        rows = [{'trial': 1, 'role': 'baseline', 'hashes_per_second': 100},
                {'trial': 1, 'role': 'candidate', 'hashes_per_second': 110},
                {'trial': 2, 'role': 'candidate', 'hashes_per_second': 90},
                {'trial': 2, 'role': 'baseline', 'hashes_per_second': 100},
                {'trial': 3, 'role': 'candidate', 'hashes_per_second': 100000}]
        summary = bench.compare_pairs(rows)
        self.assertEqual(len(summary['pairs']), 2)
        self.assertAlmostEqual(summary['median_paired_gain_percent'], 0)


class BundleIdentity(unittest.TestCase):
    def fixture(self, path):
        root = Path(path)
        (root / 'build').mkdir()
        (root / 'evidence').mkdir()
        (root / 'source.c').write_text('retained test fixture\n')
        (root / 'SOURCE-MANIFEST.json').write_text(json.dumps({'version': 'fixture', 'files':
            {'source.c': bench.digest(root / 'source.c')}}))
        lib = root / 'build/liboverxelis.so'
        lib.write_bytes(b'identity fixture, not an executable')
        (root / 'build/build.json').write_text(json.dumps({'status': 'built_pending_qualification',
            'source_manifest_sha256': bench.digest(root / 'SOURCE-MANIFEST.json'),
            'library_sha256': bench.digest(lib)}))
        (root / 'evidence/kernel-qualification.json').write_text(json.dumps({'passed': True,
            'cases': 1031, 'library_sha256': bench.digest(lib)}))
        return root

    def test_matching_identity(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.fixture(d)
            self.assertEqual(bench.verified_bundle(root)['version'], 'fixture')

    def test_modified_source_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.fixture(d)
            (root / 'source.c').write_text('changed')
            with self.assertRaisesRegex(RuntimeError, 'Source checksum mismatch'):
                bench.verified_bundle(root)

    def test_modified_library_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.fixture(d)
            (root / 'build/liboverxelis.so').write_bytes(b'changed')
            with self.assertRaisesRegex(RuntimeError, 'identity mismatch'):
                bench.verified_bundle(root)

    def test_failed_qualification_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.fixture(d)
            (root / 'evidence/kernel-qualification.json').write_text(json.dumps({'passed': False}))
            with self.assertRaisesRegex(RuntimeError, 'identity mismatch'):
                bench.verified_bundle(root)

    def test_manifest_parent_traversal_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.fixture(d)
            (root / 'SOURCE-MANIFEST.json').write_text(json.dumps({'files': {'../outside': 'bad'}}))
            with self.assertRaisesRegex(RuntimeError, 'Unsafe or missing'):
                bench.verified_bundle(root)


if __name__ == '__main__':
    unittest.main(verbosity=2)
