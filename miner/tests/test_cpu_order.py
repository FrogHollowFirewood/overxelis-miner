"""Ordered public worker selection; mocked native/network calls only."""
from contextlib import ExitStack, redirect_stdout
from io import StringIO
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import overxelis as app
import topology

SETTINGS = {'wallet': 'xel:' + 'q' * 59, 'pool': 'stratum+tcp://pool.invalid:7019',
            'worker': 'tester-1', 'password': 'x', 'threads': 3, 'page_mode': 'ordinary'}
RECORDS = [topology.CPU(cpu, (cpu,), 0, (cpu,)) for cpu in (2, 5, 9, 12)]


class OrderedSelectionTests(unittest.TestCase):
    def test_exact_requested_order_is_preserved(self):
        order = [12, 2, 9]
        selected = topology.select_ordered(3, order, RECORDS)
        self.assertEqual(selected, order)
        self.assertIsNot(selected, order)
    def test_absent_or_null_keeps_original_automatic_order(self):
        expected = topology.select(3, records=RECORDS)
        self.assertEqual(topology.select_ordered(3, records=RECORDS), expected)
        self.assertEqual(topology.select_ordered(3, None, RECORDS), expected)
    def test_unknown_or_disallowed_cpu_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'outside the process affinity'):
            topology.select_ordered(3, [12, 2, 8], RECORDS)
    def test_duplicate_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'duplicates'):
            topology.select_ordered(3, [2, 2, 9], RECORDS)
    def test_length_must_equal_threads(self):
        for cpus in ([], [2], [2, 5, 9, 12]):
            with self.subTest(cpus=cpus), self.assertRaisesRegex(ValueError, 'length equals threads'):
                topology.select_ordered(3, cpus, RECORDS)
    def test_identifiers_require_real_integers(self):
        for bad in (True, False, 2.0, '2', None, -1, 1024):
            with self.subTest(cpu=bad), self.assertRaisesRegex(ValueError, 'integer CPU identifiers'):
                topology.select_ordered(3, [bad, 5, 9], RECORDS)
    def test_json_array_required_for_explicit_order(self):
        for bad in ('12,2,9', {12, 2, 9}, (12, 2, 9), {'cpu': 2}, False):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                topology.select_ordered(3, bad, RECORDS)
    def test_config_shape_validation_does_not_read_topology_or_mutate_input(self):
        settings = {**SETTINGS, 'cpus': [12, 2, 9]}
        with patch.object(topology, 'inspect', side_effect=AssertionError('topology read')):
            checked = app.validate_settings(settings)
        self.assertEqual(settings['cpus'], [12, 2, 9])
        self.assertEqual(checked['cpus'], [12, 2, 9])
        self.assertIsNot(checked['cpus'], settings['cpus'])
    def test_legacy_string_parser_behavior_stays_sorted(self):
        self.assertEqual(topology.select(3, '12,2,9', RECORDS), [2, 9, 12])


class PublicApplicationTests(unittest.TestCase):
    def check(self, settings):
        output = StringIO()
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / 'config.json'; config.write_text(json.dumps(settings))
            with patch.object(app, 'verify_package'), patch.object(topology, 'inspect', return_value=RECORDS), \
                 patch.object(app.miner, 'load_native') as native, \
                 patch.object(app.miner, 'NativeEngine') as engine, \
                 patch.object(app.fee, 'run_pool') as pool, redirect_stdout(output):
                result = app.main(['--check', '--config', str(config)])
                native.assert_not_called(); engine.assert_not_called(); pool.assert_not_called()
        return result, output.getvalue()
    def test_check_reports_order_without_hashing_or_networking(self):
        code, output = self.check({**SETTINGS, 'cpus': [12, 2, 9]})
        self.assertEqual(code, 0)
        report = json.loads(output)
        self.assertEqual(report['cpus'], [12, 2, 9])
        self.assertFalse(report['hashing_started']); self.assertFalse(report['network_started'])
    def test_check_default_and_null_remain_identical(self):
        first_code, first = self.check(SETTINGS)
        null_code, second = self.check({**SETTINGS, 'cpus': None})
        self.assertEqual((first_code, null_code), (0, 0))
        self.assertEqual(json.loads(first), json.loads(second))
    def test_invalid_affinity_is_rejected_before_native_load(self):
        code, _ = self.check({**SETTINGS, 'cpus': [12, 2, 8]})
        self.assertEqual(code, 1)
    def test_actual_invalid_affinity_fails_before_hashing_or_networking(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / 'config.json'
            config.write_text(json.dumps({**SETTINGS, 'cpus': [12, 2, 8]}))
            with patch.object(app, 'verify_package'), patch.object(topology, 'inspect', return_value=RECORDS), \
                 patch.object(app.miner, 'load_native') as native, \
                 patch.object(app.miner, 'NativeEngine') as engine, patch.object(app.fee, 'run_pool') as pool:
                code = app.main(['--config', str(config), '--accept-dev-fee'])
                self.assertEqual(code, 1)
                native.assert_not_called(); engine.assert_not_called(); pool.assert_not_called()
    def test_actual_launch_forwards_exact_order_to_native_engine(self):
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            root = Path(folder)
            (root / 'build').mkdir(); (root / 'evidence').mkdir()
            (root / 'build/build.json').write_text(json.dumps({
                'status': 'built_pending_qualification', 'library_sha256': 'mock-sha',
                'source_manifest_sha256': 'mock-sha'}))
            (root / 'evidence/kernel-qualification.json').write_text(json.dumps({
                'passed': True, 'library_sha256': 'mock-sha'}))
            config = root / 'config.json'; config.write_text(json.dumps({**SETTINGS, 'cpus': [12, 2, 9]}))
            native_engine = MagicMock(); native_engine.pages.return_value = 0
            loader = MagicMock(); loader.nx_selftest.return_value = 0
            for name, value in (('ROOT', root), ('verify_package', MagicMock()),
                                ('platform_check', MagicMock()), ('take_lock', MagicMock(return_value=None)),
                                ('conflict_check', MagicMock()), ('sha', MagicMock(return_value='mock-sha')),
                                ('Logger', MagicMock())):
                stack.enter_context(patch.object(app, name, value))
            stack.enter_context(patch.object(topology, 'inspect', return_value=RECORDS))
            stack.enter_context(patch.object(app.signal, 'signal'))
            stack.enter_context(patch.object(app.miner, 'load_native', return_value=loader))
            engine = stack.enter_context(patch.object(app.miner, 'NativeEngine', return_value=native_engine))
            pool = stack.enter_context(patch.object(app.fee, 'run_pool'))
            code = app.main(['--config', str(config), '--accept-dev-fee', '--duration', '1'])
            self.assertEqual(code, 0)
            engine.assert_called_once_with([12, 2, 9], 1, 0, root / 'build/liboverxelis.so')
            self.assertEqual(pool.call_args.args[0], native_engine)
            native_engine.close.assert_called_once_with()


if __name__ == '__main__':
    unittest.main(verbosity=2)
