#!/usr/bin/env python3
"""Build the source preview on the mining computer as a normal user."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from public_common import need, sha, utc, verify_package, atomic_json, platform_check, conflict_check, take_lock

SOURCES = [
 ('vendor/xelis_hash_ref.c','reference'),
 ('experiments/dispatch_round_specialized.c','selected'),
 ('kernels/experimental.c','experimental'),
 ('kernels/experimental_sqrt.c','experimental_sqrt'),
 ('experiments/runtime-topology-colored-huge.c','runtime'),
 ('vendor/BLAKE3/c/blake3.c','blake3'),
 ('vendor/BLAKE3/c/blake3_dispatch.c','blake3_dispatch'),
 ('vendor/BLAKE3/c/blake3_portable.c','blake3_portable'),
 ('vendor/ChaCha20-SIMD/chacha20.c','chacha20'),
 ('vendor/ChaCha20-SIMD/chacha20_dispatch.c','chacha20_dispatch'),
 ('vendor/ChaCha20-SIMD/cpu_features.c','cpu_features')]

SELECTED_FLAGS = ('-Dxelis_hash_v3_round_specialized=xelis_hash_v3_opt', '-fno-crossjumping', '-Werror=uninitialized', '-Werror=maybe-uninitialized')
REQUIRED_EXPORTS = frozenset(('xelis_hash_v3', 'xelis_hash_v3_opt',
    'xelis_hash_v3_experimental', 'xelis_hash_v3_exp_sqrt', 'nx_create',
    'nx_destroy', 'nx_set_job', 'nx_pause', 'nx_pop', 'nx_count',
    'nx_dropped', 'nx_pages', 'nx_hash', 'nx_selftest',
    'xelis_hash_v3_opt_checked', 'nx_skipped', 'nx_bad_input'))

def compile_argv(cc, flags, source, obj):
    extra = SELECTED_FLAGS if source == 'experiments/dispatch_round_specialized.c' else ()
    return [cc, *flags, *extra, '-c', source, '-o', str(obj)]

def pgo_generate_flags(flags, profile):
    return [*flags, '-fprofile-generate='+str(profile)]


def pgo_use_flags(flags, profile):
    return [*flags, '-fprofile-use='+str(profile), '-Werror=missing-profile', '-Werror=coverage-mismatch']


def link_argv(cc, objects, library):
    return [cc, *map(str, objects), '-shared', '-pthread', '-lm',
            '-Wl,--no-undefined', '-Wl,-z,noexecstack', '-o', str(library)]

def verify_export_names(output):
    found = {line.split()[-1] for line in output.splitlines() if line.split()}
    missing = REQUIRED_EXPORTS - found
    need(not missing, 'Native library missing exports: ' + ', '.join(sorted(missing)))
    return sorted(REQUIRED_EXPORTS)

PGO_TRAINING_CODE = """
from pathlib import Path
import sys
sys.path.insert(0, sys.argv[1])
from public_common import atomic_json, sha, utc, verify_package
import qualify_public
root = Path(sys.argv[1])
library = Path(sys.argv[2])
verify_package(root)
report = qualify_public.check_corpus(library, names=('xelis_hash_v3', 'xelis_hash_v3_opt'), max_seconds=120)
report.update(utc=utc(), passed=True, single_thread=True, mining_workers_started=False,
              network_used=False, library_sha256=sha(library),
              source_manifest_sha256=sha(root/'SOURCE-MANIFEST.json'))
atomic_json(Path(sys.argv[3]), report)
print('PASS: PGO training verified 1,031 saved hash answers and full reference scratchpads.', flush=True)
"""


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', default='gcc', help='GCC executable name or path; defaults to gcc without changing system settings')
    parser.add_argument('--pgo', action='store_true',
                        help='Optional offline selected-kernel profile-guided optimization; normal qualification still required')
    args = parser.parse_args(argv)
    host = socket.gethostname().split('.')[0]
    platform_check()
    lock_fd = take_lock()  # Held for this process; released by the OS on exit.
    conflict_check()
    need(platform.machine() == 'x86_64' and sys.version_info >= (3,10), 'Linux x86-64 / Python 3.10+ required')
    need(' aes ' in ' ' + Path('/proc/cpuinfo').read_text().replace('\n',' ') + ' ', 'AES-NI required')
    verify_package(ROOT)
    cc = shutil.which(args.compiler)
    need(cc is not None, 'Requested GCC executable was not found; install the build prerequisites or choose --compiler')
    nm = shutil.which('nm')
    need(nm is not None, 'GNU nm is required to verify the native interface')
    out = ROOT / 'build'
    need(not out.exists(), 'Build output already exists; do not overwrite qualification evidence')
    out.mkdir()
    record = {'host':host,'started_utc':utc(),'status':'building','commands':[],
              'source_manifest_sha256':sha(ROOT/'SOURCE-MANIFEST.json'),
              'compiler_requested':args.compiler,'compiler_path':cc,'compiler_realpath':str(Path(cc).resolve()),
              'compiler':subprocess.check_output([cc,'--version'],text=True).splitlines()[0]}
    os.nice(10)  # One compiler at a time, lower priority; this affects this child only.
    flags = ['-O3','-fno-math-errno','-std=gnu11','-fPIC','-pthread','-maes','-mpclmul','-march=native',
             '-Wall','-Wextra','-Wno-unused-parameter','-Wno-pointer-sign',
             '-Iinclude','-Ivendor','-Ivendor/BLAKE3/c','-Ivendor/ChaCha20-SIMD']
    objects = []
    def command(args, label):
        started = time.monotonic()
        log = out/(label+'.log')
        entry = {'argv':args,'log':str(log), 'cwd':str(ROOT),'timeout_seconds':180,
                 'argv_sha256':hashlib.sha256(json.dumps(args, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()}
        record['commands'].append(entry)
        atomic_json(out/'build.json',record)
        try:
            with log.open('x') as f:
                result = subprocess.run(args,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=180)
            entry['returncode'] = result.returncode
        except BaseException as error:
            entry['error'] = type(error).__name__+': '+str(error)
            raise
        finally:
            entry['elapsed_seconds'] = time.monotonic()-started
            if log.is_file(): entry['log_sha256'] = sha(log)
            atomic_json(out/'build.json',record)
        need(result.returncode == 0, 'Build command failed; inspect ' + str(log))
    try:
        profile = out/'pgo-profile'
        if args.pgo:
            profile.mkdir(mode=0o700)
            record['pgo'] = {'enabled':True, 'training_source':'retained 1031-input corpus only',
                             'profile_directory':str(profile), 'training_wall_limit_seconds':120,
                             'inputs_sha256':sha(ROOT/'reference/rig-golden-inputs.txt'),
                             'expected_sha256':sha(ROOT/'reference/rig-rust-hashes.txt'),
                             'instrumented_sources':['experiments/dispatch_round_specialized.c']}
        else:
            record['pgo'] = {'enabled':False}
        for source,name in SOURCES:
            print('Compiling '+source,flush=True)
            obj = out/(name+'.o')
            selected_flags = pgo_generate_flags(flags,profile) if args.pgo and name == 'selected' else flags
            command(compile_argv(cc,selected_flags,source,obj),name); objects.append(obj)
        for isa in ('sse2','avx2'):
            obj = out/('chacha20_'+isa+'.o')
            command([cc,*flags,'-m'+isa,'-c','vendor/ChaCha20-SIMD/chacha20_'+isa+'.c','-o',str(obj)],'chacha20_'+isa)
            objects.append(obj)
        for isa in ('sse2','sse41','avx2','avx512'):
            obj=out/('blake3_'+isa+'.o')
            command([cc,'-fPIC','-c','vendor/BLAKE3/c/blake3_'+isa+'_x86-64_unix.S','-o',str(obj)],'blake3_'+isa)
            objects.append(obj)
        if args.pgo:
            instrumented = out/'liboverxelis-training.so'
            command([cc, '-fprofile-generate='+str(profile), *link_argv(cc,objects,instrumented)[1:]], 'pgo-training-link')
            record['pgo'].update(instrumented_library_sha256=sha(instrumented),
                                 instrumented_selected_object_sha256=sha(out/'selected.o'),
                                 training_code_sha256=hashlib.sha256(PGO_TRAINING_CODE.encode()).hexdigest())
            training_report = out/'pgo-training.json'
            command([sys.executable, '-I', '-B', '-c', PGO_TRAINING_CODE,
                     str(ROOT), str(instrumented), str(training_report)], 'pgo-training')
            trained = json.loads(training_report.read_text())
            need(trained.get('passed') is True and trained.get('cases') == 1031 and
                 trained.get('library_sha256') == sha(instrumented), 'PGO training failed validation')
            # The child has exited, so GCC has flushed its profile. Do not use an
            # empty/partial profile, change the object pathname, or hide GCC warnings.
            profiles = sorted(profile.rglob('*.gcda'))
            need(profiles and all(p.is_file() and not p.is_symlink() and p.stat().st_size > 0 for p in profiles),
                 'PGO child produced no complete profile data')
            record['pgo'].update(training_report_sha256=sha(training_report),
                                 profile_hashes={str(p.relative_to(out)):sha(p) for p in profiles})
            use_flags = pgo_use_flags(flags,profile)
            command(compile_argv(cc,use_flags,'experiments/dispatch_round_specialized.c',out/'selected.o'), 'pgo-selected-use')
            need(record['pgo']['profile_hashes'] == {str(p.relative_to(out)):sha(p) for p in profiles},
                 'PGO profile changed during final compilation')
            record['pgo']['final_selected_object_sha256'] = sha(out/'selected.o')
        lib=out/'liboverxelis.so'
        command(link_argv(cc,objects,lib),'link')
        command([nm,'-D','--defined-only',str(lib)],'exports')
        record['verified_native_exports'] = verify_export_names((out/'exports.log').read_text())
        record['selected_compile_flags'] = list(SELECTED_FLAGS)
        record['strict_undefined_symbol_check'] = True
        record['packaging_revision'] = 'public-source-preview.2'
        verify_package(ROOT)
        record.update(status='built_pending_qualification',finished_utc=utc(),library_sha256=sha(lib),
                      cpu_info=Path('/proc/cpuinfo').read_text().split('\n\n')[0],objects={x.name:sha(x) for x in objects})
    except BaseException as e:
        record.update(status='failed_preserved',error=type(e).__name__+': '+str(e),finished_utc=utc())
        raise
    finally: atomic_json(out/'build.json',record)
    print('Local compilation complete. Run qualify_public.py next; mining has not started.',flush=True)

if __name__ == '__main__': main()
