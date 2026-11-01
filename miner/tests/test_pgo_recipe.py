"""Exercise the real GCC profile-flush/use recipe with a tiny non-hashing DSO."""
from pathlib import Path
import importlib.util
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pgo_build_recipe', ROOT / 'build_public.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class GCCProfileRecipe(unittest.TestCase):
    def test_flushed_profile_consumed_and_missing_profile_fails(self):
        cc = shutil.which('gcc')
        if cc is None:
            self.skipTest('GCC required')
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / 'experiments/dispatch_round_specialized.c'
            source.parent.mkdir()
            source.write_text('int xelis_hash_v3_round_specialized(int x) {\n'
                              ' int y=0; for(int i=0;i<x;i++) y += i%3 ? i : 2*i; return y;\n}\n')
            profile = root / 'profile'
            profile.mkdir()
            obj = root / 'selected.o'
            lib = root / 'training.so'
            flags = ['-O2', '-fPIC']
            def command(args):
                return subprocess.run(args, cwd=root, capture_output=True, text=True, timeout=30)
            generated = command(build.compile_argv(cc, build.pgo_generate_flags(flags, profile),
                                'experiments/dispatch_round_specialized.c', obj))
            self.assertEqual(generated.returncode, 0, generated.stderr)
            linked = command([cc, '-fprofile-generate='+str(profile), *build.link_argv(cc,[obj],lib)[1:]])
            self.assertEqual(linked.returncode, 0, linked.stderr)
            trained = command([sys.executable, '-I', '-B', '-c',
                'import ctypes,sys; lib=ctypes.CDLL(sys.argv[1]); f=lib.xelis_hash_v3_opt; '
                'f.argtypes=[ctypes.c_int]; f.restype=ctypes.c_int; '
                'assert f(10)==63; assert f(20)==253', str(lib)])
            self.assertEqual(trained.returncode, 0, trained.stderr)
            profiles = list(profile.rglob('*.gcda'))
            self.assertTrue(profiles, 'child exit must flush GCC profile data')
            used = command(build.compile_argv(cc, build.pgo_use_flags(flags, profile),
                           'experiments/dispatch_round_specialized.c', obj))
            self.assertEqual(used.returncode, 0, used.stderr)
            original = source.read_text()
            source.write_text('int xelis_hash_v3_round_specialized(int x) { return x > 100 ? x*3 : x*2; }\n')
            mismatch = command(build.compile_argv(cc, build.pgo_use_flags(flags, profile),
                               'experiments/dispatch_round_specialized.c', obj))
            self.assertNotEqual(mismatch.returncode, 0, 'incompatible profile must fail')
            self.assertIn('coverage-mismatch', mismatch.stderr)
            source.write_text(original)
            for p in profiles:
                p.unlink()
            missing = command(build.compile_argv(cc, build.pgo_use_flags(flags, profile),
                              'experiments/dispatch_round_specialized.c', obj))
            self.assertNotEqual(missing.returncode, 0, 'missing profile must never silently fall back')
            self.assertIn('missing-profile', missing.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
