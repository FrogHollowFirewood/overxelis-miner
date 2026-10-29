#!/usr/bin/env python3
"""Build the source preview on the mining computer as a normal user."""
from pathlib import Path
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

SELECTED_FLAGS = ('-Dxelis_hash_v3_round_specialized=xelis_hash_v3_opt', '-fno-crossjumping')
REQUIRED_EXPORTS = frozenset(('xelis_hash_v3', 'xelis_hash_v3_opt',
    'xelis_hash_v3_experimental', 'xelis_hash_v3_exp_sqrt', 'nx_create',
    'nx_destroy', 'nx_set_job', 'nx_pause', 'nx_pop', 'nx_count',
    'nx_dropped', 'nx_pages', 'nx_hash', 'nx_selftest'))

def compile_argv(cc, flags, source, obj):
    extra = SELECTED_FLAGS if source == 'experiments/dispatch_round_specialized.c' else ()
    return [cc, *flags, *extra, '-c', source, '-o', str(obj)]

def link_argv(cc, objects, library):
    return [cc, *map(str, objects), '-shared', '-pthread', '-lm',
            '-Wl,--no-undefined', '-Wl,-z,noexecstack', '-o', str(library)]

def verify_export_names(output):
    found = {line.split()[-1] for line in output.splitlines() if line.split()}
    missing = REQUIRED_EXPORTS - found
    need(not missing, 'Native library missing exports: ' + ', '.join(sorted(missing)))
    return sorted(REQUIRED_EXPORTS)

def main():
    host = socket.gethostname().split('.')[0]
    platform_check()
    lock_fd = take_lock()  # Held for this process; released by the OS on exit.
    conflict_check()
    need(platform.machine() == 'x86_64' and sys.version_info >= (3,10), 'Linux x86-64 / Python 3.10+ required')
    need(' aes ' in ' ' + Path('/proc/cpuinfo').read_text().replace('\n',' ') + ' ', 'AES-NI required')
    verify_package(ROOT)
    cc = shutil.which('gcc')
    need(cc is not None, 'GCC is missing; install the rig build prerequisites before retrying')
    nm = shutil.which('nm')
    need(nm is not None, 'GNU nm is required to verify the native interface')
    out = ROOT / 'build'
    need(not out.exists(), 'Build output already exists; do not overwrite qualification evidence')
    out.mkdir()
    record = {'host':host,'started_utc':utc(),'status':'building','commands':[],
              'source_manifest_sha256':sha(ROOT/'SOURCE-MANIFEST.json'),'compiler':subprocess.check_output([cc,'--version'],text=True).splitlines()[0]}
    os.nice(10)  # One compiler at a time, lower priority; this affects this child only.
    flags = ['-O3','-fno-math-errno','-std=gnu11','-fPIC','-pthread','-maes','-mpclmul','-march=native',
             '-Wall','-Wextra','-Wno-unused-parameter','-Wno-pointer-sign',
             '-Iinclude','-Ivendor','-Ivendor/BLAKE3/c','-Ivendor/ChaCha20-SIMD']
    objects = []
    def command(args, label):
        log = out/(label+'.log')
        with log.open('x') as f:
            result = subprocess.run(args,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=180)
        record['commands'].append({'argv':args,'returncode':result.returncode,'log':str(log),'log_sha256':sha(log)})
        atomic_json(out/'build.json',record)
        need(result.returncode == 0, 'Compilation failed; inspect ' + str(log))
    try:
        for source,name in SOURCES:
            print('Compiling '+source,flush=True)
            obj = out/(name+'.o'); command(compile_argv(cc,flags,source,obj),name); objects.append(obj)
        for isa in ('sse2','avx2'):
            obj = out/('chacha20_'+isa+'.o')
            command([cc,*flags,'-m'+isa,'-c','vendor/ChaCha20-SIMD/chacha20_'+isa+'.c','-o',str(obj)],'chacha20_'+isa)
            objects.append(obj)
        for isa in ('sse2','sse41','avx2','avx512'):
            obj=out/('blake3_'+isa+'.o')
            command([cc,'-fPIC','-c','vendor/BLAKE3/c/blake3_'+isa+'_x86-64_unix.S','-o',str(obj)],'blake3_'+isa)
            objects.append(obj)
        lib=out/'liboverxelis.so'
        command(link_argv(cc,objects,lib),'link')
        command([nm,'-D','--defined-only',str(lib)],'exports')
        record['verified_native_exports'] = verify_export_names((out/'exports.log').read_text())
        record['selected_compile_flags'] = list(SELECTED_FLAGS)
        record['strict_undefined_symbol_check'] = True
        record['packaging_revision'] = 'public-source-preview.1'
        verify_package(ROOT)
        record.update(status='built_pending_qualification',finished_utc=utc(),library_sha256=sha(lib),
                      cpu_info=Path('/proc/cpuinfo').read_text().split('\n\n')[0],objects={x.name:sha(x) for x in objects})
    except BaseException as e:
        record.update(status='failed_preserved',error=type(e).__name__+': '+str(e),finished_utc=utc())
        raise
    finally: atomic_json(out/'build.json',record)
    print('Local compilation complete. Run qualify_public.py next; mining has not started.',flush=True)

if __name__ == '__main__': main()
