#!/usr/bin/env python3
"""Force the selected zero-modulus guard in a separate correctness-only library.

No pool or user configuration is used. Production sources, objects and library
are read only; every generated file goes in a fresh evidence directory.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from public_common import (atomic_json, conflict_check, need, platform_check,
                           sha, take_lock, utc, verify_package)

GUARD = '        if (__builtin_expect(result == 0, 0)) return -1;'
SELECTED = 'experiments/dispatch_round_specialized.c'

# Each case is a separate process so its entire native lifetime, including
# worker creation/cleanup, has a 15-second wall limit enforced by the parent.
CASE_CODE = r'''
import ctypes as C, json, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import miner, topology
n = int(sys.argv[3]); mode = sys.argv[4]; engine = None
result = {'threads': n, 'page_mode': mode, 'passed': False}
try:
    engine = miner.NativeEngine(topology.select(n), 1, miner.PAGES[mode], Path(sys.argv[2]))
    assert engine.pages() == (n if mode == 'hugetlb' else 0), 'Requested memory mode unavailable'
    lib = engine.lib
    lib.nx_skipped.argtypes, lib.nx_skipped.restype = [C.c_void_p], C.c_uint64
    lib.nx_bad_input.argtypes, lib.nx_bad_input.restype = [C.c_void_p, C.c_void_p], C.c_int
    blob = bytes((i * 173 + 91) & 255 for i in range(112))
    start = (1 << 64) - n
    engine.set_job(blob, bytes([255]) * 32, 0x4f584d04, start)
    deadline = time.monotonic() + 12
    while lib.nx_skipped(engine.handle) < n:
        assert time.monotonic() < deadline, 'Skipped-input publication deadline exceeded'
        assert engine.count() == 0, 'Failed input counted as completed work'
        assert engine.pop() is None, 'Failed input queued a share'
        time.sleep(.001)
    engine.pause()
    skipped = lib.nx_skipped(engine.handle)
    assert skipped == n, 'Workers did not consume exactly one terminal nonce each'
    assert engine.count() == 0 and engine.dropped() == 0 and engine.pop() is None, 'Invalid failure accounting'
    captured = C.create_string_buffer(112)
    assert lib.nx_bad_input(engine.handle, captured) == 1, 'First failing input was not captured'
    captured = captured.raw
    nonce = int.from_bytes(captured[40:48], 'big')
    assert start <= nonce < (1 << 64), 'Captured nonce outside terminal range'
    assert captured[:40] + captured[48:] == blob[:40] + blob[48:], 'Captured job bytes changed'
    result.update(passed=True, completed_hashes=0, skipped_inputs=skipped,
                  queued_shares=0, dropped_shares=0, captured_nonce=nonce,
                  nonce_start=start, nonce_end=(1 << 64)-1, huge_page_workers=engine.pages())
finally:
    if engine is not None:
        try: engine.pause()
        finally: engine.close()
print(json.dumps(result))
'''


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', required=True, type=Path,
                        help='Absolute path to a trusted GCC 15 executable')
    parser.add_argument('--threads', type=int, nargs='+', default=[1, 24, 32, 192])
    parser.add_argument('--page-mode', choices=('ordinary', 'hugetlb'), default='ordinary')
    args = parser.parse_args(argv)
    lock = folder = None
    previous_signals = {}
    report = {'started_utc': utc(), 'passed': False, 'network_used': False,
              'pool_configuration_used': False, 'throughput_benchmark': False,
              'cases': [], 'page_mode': args.page_mode}
    pins = {}
    try:
        def interrupted(*_):
            raise KeyboardInterrupt
        for name in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            previous_signals[name] = signal.signal(name, interrupted)
        need(args.threads and len(set(args.threads)) == len(args.threads) and
             all(1 <= n <= 1024 for n in args.threads), 'Choose distinct thread counts from 1 to 1024')
        platform_check()
        lock = take_lock()
        conflict_check()
        verify_package(ROOT)
        compiler = args.compiler
        need(compiler.is_absolute() and compiler.is_file() and os.access(compiler, os.X_OK),
             'Provide the absolute path of a trusted GCC 15 executable')
        version = subprocess.check_output([str(compiler), '-dumpfullversion'], text=True, timeout=15).strip()
        need(version.split('.')[0] == '15', 'This reproducer requires GCC 15; requested compiler reports ' + version)
        build = json.loads((ROOT / 'build/build.json').read_text())
        library = ROOT / 'build/liboverxelis.so'
        need(build.get('status') == 'built_pending_qualification', 'Complete a normal build first')
        need(build.get('source_manifest_sha256') == sha(ROOT / 'SOURCE-MANIFEST.json') and
             build.get('library_sha256') == sha(library), 'Build/source/library identity mismatch')
        need(not build.get('pgo', {}).get('enabled'), 'Use a normal non-PGO build for this reproducer')
        commands = [entry['argv'] for entry in build['commands']
                    if isinstance(entry.get('argv'), list) and SELECTED in entry['argv'] and '-c' in entry['argv']]
        need(len(commands) == 1, 'Expected exactly one normal selected-kernel compile command')
        command = list(commands[0])
        need(all(isinstance(x, str) for x in command) and command.count('-c') == command.count('-o') == 1,
             'Unexpected selected-kernel compile command')
        need(command[command.index('-c') + 1] == SELECTED, 'Selected compile command source mismatch')
        object_names = build.get('objects', {})
        objects = sorted((ROOT / 'build').glob('*.o'))
        need('selected.o' in object_names and {p.name for p in objects} == set(object_names),
             'Build objects are missing or contain unrecorded objects; rebuild normally')
        for path in objects:
            need(path.is_file() and not path.is_symlink() and sha(path) == object_names[path.name],
                 'Build object checksum mismatch: ' + path.name)
        source_path = ROOT / SELECTED
        source = source_path.read_text()
        need(source.count(GUARD) == 1, 'Expected exactly one selected zero-modulus guard; refusing uncertain injection')
        pinned = [ROOT / 'SOURCE-MANIFEST.json', ROOT / 'build/build.json', library, source_path, *objects]
        pins = {str(path.relative_to(ROOT)): sha(path) for path in pinned}
        evidence = ROOT / 'evidence'
        need(not evidence.is_symlink(), 'Evidence directory must not be a symlink')
        evidence.mkdir(mode=0o700, exist_ok=True)
        folder = Path(tempfile.mkdtemp(prefix='zero-modulus-', dir=evidence))
        forced_source, forced_object = folder / 'forced-selected.c', folder / 'forced-selected.o'
        forced_library = folder / 'liboverxelis-forced-zero.so'
        forced_source.write_text(source.replace(GUARD, '        result = 0; /* TEST COPY ONLY */\n' + GUARD))
        command[0] = str(compiler)
        command[command.index('-c') + 1] = str(forced_source)
        command[command.index('-o') + 1] = str(forced_object)
        report.update(compiler=str(compiler), compiler_version=version,
                      source_manifest_sha256=pins['SOURCE-MANIFEST.json'],
                      production_library_sha256=pins['build/liboverxelis.so'],
                      selected_source_sha256=pins[SELECTED], forced_source_sha256=sha(forced_source),
                      test_directory=str(folder), injection='Force result=0 immediately before the selected zero-modulus guard')
        link = [str(compiler), *map(str, (p for p in objects if p.name != 'selected.o')),
                str(forced_object), '-shared', '-pthread', '-lm', '-Wl,--no-undefined',
                '-Wl,-z,noexecstack', '-o', str(forced_library)]
        for label, arguments in [('compile', command), ('link', link)]:
            with (folder / (label + '.log')).open('x') as log:
                completed = subprocess.run(arguments, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=180)
            need(completed.returncode == 0, label + ' failed; inspect ' + str(folder / (label + '.log')))
        report['forced_library_sha256'] = sha(forced_library)
        import ctypes as C
        import errno
        lib = C.CDLL(str(forced_library), use_errno=True)
        lib.nx_hash.argtypes, lib.nx_hash.restype = [C.c_void_p, C.c_void_p, C.c_int], C.c_int
        output = C.create_string_buffer(b'X' * 32, 32)
        C.set_errno(0)
        status = lib.nx_hash(C.create_string_buffer(bytes(112)), output, 1)
        need(status == -1 and C.get_errno() == errno.EDOM and output.raw == b'X' * 32,
             'Forced nx_hash did not fail with EDOM and untouched output')
        report['single_hash'] = {'status': status, 'errno': C.get_errno(), 'output_untouched': True}
        for count in args.threads:
            result = subprocess.run([sys.executable, '-I', '-B', '-c', CASE_CODE, str(ROOT),
                                     str(forced_library), str(count), args.page_mode],
                                    capture_output=True, text=True, timeout=15)
            (folder / ('workers-%d.log' % count)).write_text(result.stdout + result.stderr)
            need(result.returncode == 0, 'Forced worker case failed for %d threads; inspect its evidence log' % count)
            case = json.loads(result.stdout)
            need(case.get('passed') is True, 'Forced worker case did not pass')
            report['cases'].append(case)
        verify_package(ROOT)
        need(all(sha(ROOT / name) == digest for name, digest in pins.items()),
             'Production source/build identity changed during correctness testing')
        report.update(passed=True, production_files_unchanged=True)
        print('PASS: forced zero-modulus guard; %s workers; no completed hashes or queued shares.' %
              ', '.join(str(n) for n in args.threads), flush=True)
        return 0
    except (Exception, KeyboardInterrupt) as error:
        report.update(passed=False, error=type(error).__name__ + ': ' + str(error))
        print('ZERO-MODULUS TEST STOPPED: ' + report['error'], file=sys.stderr, flush=True)
        return 130 if isinstance(error, KeyboardInterrupt) else 1
    finally:
        try:
            if folder is not None:
                report['finished_utc'] = utc()
                atomic_json(folder / 'result.json', report)
                print('Evidence: ' + str(folder / 'result.json'), flush=True)
        finally:
            if lock is not None:
                os.close(lock)
            for name, handler in previous_signals.items():
                signal.signal(name, handler)


if __name__ == '__main__':
    raise SystemExit(main())
