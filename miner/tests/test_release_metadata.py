"""Release inventory checks; no native hashing or public network traffic."""
from pathlib import Path
import json,sys,unittest
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
import public_common as c
import build_public as b
class ReleaseInventory(unittest.TestCase):
 def test_edition(self):
  self.assertEqual(c.EDITION,'public-source-preview.2')
  self.assertEqual(json.loads((R/'SOURCE-MANIFEST.json').read_text())['edition'],c.EDITION)
 def test_attribution_paths(self):
  for item in json.loads((R/'ATTRIBUTION.json').read_text())['components']:
   for n in item.get('files',[])+item.get('license_files',[]):self.assertTrue((R/n).is_file(),n)
   for n in item.get('directories',[]):self.assertTrue((R/n).is_dir(),n)
 def test_historical_files_not_shipped(self):
  for n in json.loads((R/'ATTRIBUTION.json').read_text())['historical_not_shipped']:self.assertFalse((R/n).exists(),n)
 def test_compilation_inputs_exist(self):
  for n,_ in b.SOURCES:self.assertTrue((R/n).is_file(),n)
  readme=(R/'README.md').read_text()
  self.assertIn('sha256sum --check SHA256SUMS-public-source-preview.2.txt &&',readme)
  self.assertIn('python3 -I -B build_public.py &&',readme)
  self.assertIn('python3 -I -B qualify_public.py &&',readme)
 def test_tnn_path_disclosed_and_called(self):
  for n in ('experiments/dispatch_round_specialized.c','kernels/experimental.c','kernels/experimental_sqrt.c'):
   self.assertIn('jay_chacha8_four_wide(', (R/n).read_text())
  self.assertIn('not merely an unused comparison artifact',(R/'THIRD_PARTY_NOTICES.md').read_text())
 def test_integrity(self):c.verify_package(R)
 def test_validation_limits(self):
  v=json.loads((R/'VALIDATION.json').read_text())
  for k in ('public_native_build_run','public_native_qualification_run','public_live_pool_tested','full_live_fee_cycle_verified'):self.assertFalse(v[k],k)
 def test_unchanged_fee_policy(self):
  import overxelis_fee as fee
  self.assertEqual((fee.USER_SECONDS,fee.FEE_SECONDS),(5940,60))
if __name__=='__main__':unittest.main(verbosity=2)
