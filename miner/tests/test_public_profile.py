"""Pure optional-profile checks; no native hashing, topology inspection or network."""
from pathlib import Path
import copy
import json
import sys
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import overxelis as app

class Optional7995WXProfile(unittest.TestCase):
    def profile(self):
        return json.loads((ROOT / 'config.7995wx.example.json').read_text())
    def test_explicit_profile_has_public_placeholder_and_requested_hardware_settings(self):
        profile = self.profile()
        self.assertEqual(profile['wallet'], 'YOUR_XELIS_MAINNET_PAYOUT_ADDRESS')
        self.assertEqual(profile['threads'], 192)
        self.assertEqual(profile['page_mode'], 'hugetlb')
        self.assertIsNone(profile['cpus'])
        generic = json.loads((ROOT / 'config.example.json').read_text())
        self.assertEqual((generic['threads'], generic['page_mode']), (8, 'ordinary'))
    def test_placeholder_profile_fails_before_native_or_pool_use(self):
        with patch.object(app.miner, 'load_native') as load, patch.object(app.miner, 'NativeEngine') as engine, \
             patch.object(app.fee, 'run_pool') as pool:
            with self.assertRaisesRegex(RuntimeError, 'Enter your own mainnet'):
                app.validate_settings(self.profile())
            load.assert_not_called(); engine.assert_not_called(); pool.assert_not_called()
    def test_public_address_shape_validates_without_mutating_profile_or_reading_topology(self):
        original = self.profile()
        edited = copy.deepcopy(original)
        edited['wallet'] = 'xel:' + 'q' * 59
        with patch.object(app.topology, 'inspect', side_effect=AssertionError('unexpected topology inspection')):
            checked = app.validate_settings(edited)
        self.assertEqual(checked['threads'], 192)
        self.assertIsNone(checked['cpus'])
        self.assertEqual(original['wallet'], 'YOUR_XELIS_MAINNET_PAYOUT_ADDRESS')
        self.assertEqual(edited['wallet'], 'xel:' + 'q' * 59)

if __name__ == '__main__':
    unittest.main(verbosity=2)
