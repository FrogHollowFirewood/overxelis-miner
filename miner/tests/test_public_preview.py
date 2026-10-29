"""Public packaging checks: no native hashing, external networking or mining."""
from pathlib import Path
import importlib.util, json, os, sys, tempfile, unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import overxelis as app
import public_common as common
import build_public as build
VALID={'wallet':'xel:'+'q'*59,'pool':'stratum+tcp://pool.invalid:7019','worker':'tester-1','password':'x','threads':8,'page_mode':'ordinary'}
class Settings(unittest.TestCase):
 def test_valid(self): self.assertEqual(app.validate_settings(VALID)['threads'],8)
 def test_no_default_wallet(self):
  # Nonempty malformed addresses reach the public address-shape guard.
  for wallet in ('YOUR_XELIS_MAINNET_PAYOUT_ADDRESS','seed phrase words','xel:short'):
   with self.subTest(wallet=wallet), self.assertRaisesRegex(RuntimeError, 'Enter your own mainnet'):
    app.validate_settings({**VALID,'wallet':wallet})
 def test_empty_or_nonstring_wallet_rejected(self):
  # The unchanged protocol validator rejects these first with ValueError.
  for wallet in ('',None,False,7,[],{}):
   with self.subTest(wallet=wallet), self.assertRaisesRegex(ValueError, 'valid wallet'):
    app.validate_settings({**VALID,'wallet':wallet})
 def test_missing_wallet_rejected(self):
  value=dict(VALID);del value['wallet']
  with self.assertRaisesRegex(ValueError, 'valid wallet'):app.validate_settings(value)
 def test_bad_wallet_never_loads_native_or_starts_pool(self):
  for wallet in ('','YOUR_XELIS_MAINNET_PAYOUT_ADDRESS','seed phrase words','xel:short',None):
   with self.subTest(wallet=wallet), tempfile.TemporaryDirectory() as d:
    f=Path(d)/'c.json';f.write_text(json.dumps({**VALID,'wallet':wallet}))
    with patch.object(app,'verify_package'), patch.object(app.miner,'load_native') as native, patch.object(app.fee,'run_pool') as pool:
     self.assertEqual(app.main(['--check','--config',str(f)]),1)
     native.assert_not_called();pool.assert_not_called()
 def test_threads(self):
  for n in (True,0,-1,1025,8.0,'8'):
   with self.assertRaises(RuntimeError): app.validate_settings({**VALID,'threads':n})
 def test_pages(self):
  with self.assertRaises(RuntimeError): app.validate_settings({**VALID,'page_mode':'auto'})
 def test_worker_control_characters(self):
  for name in ('w\n','w; command','x'*65):
   with self.assertRaises((ValueError,RuntimeError)): app.validate_settings({**VALID,'worker':name})
 def test_invalid_pool(self):
  for url in ('https://pool.invalid','stratum+tcp://user:pass@pool.invalid:7019','stratum+tcp://pool.invalid:7019/path'):
   with self.assertRaises(ValueError): app.validate_settings({**VALID,'pool':url})
 def test_not_mutated(self):
  value=dict(VALID);app.validate_settings(value);self.assertEqual(value,VALID)
 def test_check_never_hashes(self):
  with tempfile.TemporaryDirectory() as d:
   f=Path(d)/'c.json';f.write_text(json.dumps(VALID))
   with patch.object(app,'verify_package'),patch.object(app.topology,'select',return_value=list(range(8))),patch.object(app.miner,'load_native') as native,patch.object(app.fee,'run_pool') as pool:
    self.assertEqual(app.main(['--check','--config',str(f)]),0);native.assert_not_called();pool.assert_not_called()
 def test_consent_required_before_native_load(self):
  with tempfile.TemporaryDirectory() as d:
   f=Path(d)/'c.json';f.write_text(json.dumps(VALID))
   with patch.object(app,'verify_package'),patch.object(app,'platform_check'),patch.object(app.miner,'load_native') as native:
    self.assertEqual(app.main(['--config',str(f)]),1);native.assert_not_called()
 def test_wizard_no_overwrite(self):
  with tempfile.TemporaryDirectory() as d, patch.object(app.sys.stdin,'isatty',return_value=True):
   f=Path(d)/'c.json';f.write_text('preserve')
   with self.assertRaises(RuntimeError):app.configure(f)
   self.assertEqual(f.read_text(),'preserve')
class BuildRecipe(unittest.TestCase):
 def test_mapping(self):
  args=build.compile_argv('gcc',[], 'experiments/dispatch_round_specialized.c','x.o')
  self.assertIn('-Dxelis_hash_v3_round_specialized=xelis_hash_v3_opt',args);self.assertIn('-fno-crossjumping',args)
 def test_reference_not_renamed(self):self.assertNotIn('-Dxelis_hash_v3_round_specialized=xelis_hash_v3_opt',build.compile_argv('gcc',[],'vendor/xelis_hash_ref.c','x.o'))
 def test_strict_linking(self):self.assertIn('-Wl,--no-undefined',build.link_argv('gcc',[],'x.so'))
 def test_missing_export_fails(self):
  with self.assertRaises(RuntimeError):build.verify_export_names('000 T nx_create')
 def test_exports(self):self.assertEqual(len(build.verify_export_names('\n'.join('000 T '+n for n in build.REQUIRED_EXPORTS))),len(build.REQUIRED_EXPORTS))
class Manifest(unittest.TestCase):
 def test_tampering_fails(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);(r/'a').write_text('one');(r/'SOURCE-MANIFEST.json').write_text(json.dumps({'version':common.VERSION,'files':{'a':common.sha(r/'a')}}))
   common.verify_package(r);(r/'a').write_text('two')
   with self.assertRaises(RuntimeError):common.verify_package(r)
 def test_parent_escape_fails(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);(r/'SOURCE-MANIFEST.json').write_text(json.dumps({'version':common.VERSION,'files':{'../x':'0'}}))
   with self.assertRaises(RuntimeError):common.verify_package(r)
 def test_symlink_fails(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);(r/'a').write_text('one');(r/'b').symlink_to(r/'a');(r/'SOURCE-MANIFEST.json').write_text(json.dumps({'version':common.VERSION,'files':{'b':common.sha(r/'a')}}))
   with self.assertRaises(RuntimeError):common.verify_package(r)
if __name__=='__main__':unittest.main(verbosity=2)
