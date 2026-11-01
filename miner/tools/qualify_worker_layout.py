#!/usr/bin/env python3
"""Qualify actual hugetlb worker scratchpads with one terminal nonce per worker."""
from pathlib import Path
import argparse
import json
import os
import re
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools'))
import benchmark_native as existing

MAX_NONCE = (1 << 64) - 1
EPOCH = 0x4F584D03


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--threads', type=int, default=192)
    parser.add_argument('--cpus', help='Optional explicit CPU list, matching --threads')
    parser.add_argument('--output', type=Path, default=ROOT / 'evidence/worker-layout-qualification.json')
    args = parser.parse_args(argv)
    report = {'started_utc': existing.utc(), 'passed': False, 'network_used': False,
              'pool_configuration_used': False, 'fresh_rust_executed': False,
              'verification_reference': 'Kernel0 C reference via NativeEngine.verify; not fresh Rust.',
              'memory_mode': 'hugetlb', 'kernel': 1, 'epoch': EPOCH,
              'script_sha256': existing.digest(Path(__file__)), 'shares': []}
    output = engine = lock = None
    previous = {}
    started = time.monotonic()
    try:
        def interrupted(*_):
            raise KeyboardInterrupt
        for name in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            previous[name] = signal.signal(name, interrupted)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        output = os.fdopen(os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'w')
        existing.platform_check()
        lock = existing.take_lock()
        existing.conflict_check()
        identity = existing.verified_bundle(ROOT)
        qualification = json.loads((ROOT / 'evidence/kernel-qualification.json').read_text())
        existing.need(qualification.get('c_implementations') == 4 and
                      qualification.get('full_scratchpad_comparisons') == 1031,
                      'Full four-kernel qualification must pass first')
        cpus = existing.topology.select(args.threads, args.cpus)
        runtime = ROOT / 'experiments/runtime-topology-colored-huge.c'
        source = runtime.read_text()
        layout = {name: int(re.search(r'#define '+name+r' \(\(size_t\)(\d+)\)', source).group(1))
                  for name in ('NX_COLOR_STRIDE', 'NX_COLOR_WINDOW')}
        report.update(identity=identity, source_manifest_sha256=identity['source_manifest_sha256'],
                      build_record_sha256=existing.digest(ROOT / 'build/build.json'),
                      kernel_qualification_sha256=existing.digest(ROOT / 'evidence/kernel-qualification.json'),
                      runtime_source_sha256=existing.digest(runtime),
                      selected_kernel_source_sha256=existing.digest(ROOT / 'experiments/dispatch_round_specialized.c'),
                      layout_constants=layout, threads=len(cpus), cpus=cpus,
                      full_kernel_qualification_previously_passed=True)
        engine = existing.miner.NativeEngine(cpus, 1, existing.miner.PAGES['hugetlb'], Path(identity['library']))
        report['huge_page_workers'] = engine.pages()
        existing.need(engine.pages() == len(cpus), 'All requested workers must use hugetlb; fallback refused')
        blob = bytes((i * 173 + 91) & 255 for i in range(112))
        nonce_start = MAX_NONCE - len(cpus) + 1
        expected = set(range(nonce_start, MAX_NONCE + 1))
        report.update(nonce_start=nonce_start, nonce_end=MAX_NONCE, target_hex='ff' * 32,
                      work_blob_hex=blob.hex(), terminal_nonces_per_worker=1)
        # Every initial nonce is above MAX_NONCE-threads. Its next increment
        # would overflow, so each worker hashes exactly once then parks.
        engine.set_job(blob, bytes([255]) * 32, EPOCH, nonce_start)
        seen = set()
        deadline = time.monotonic() + 60
        while len(seen) < len(cpus):
            existing.need(time.monotonic() < deadline, 'Worker/share publication deadline exceeded')
            row = engine.pop()
            if row is None:
                # nx_count is published before a share enters its queue.
                # Keep draining until every distinct expected share appears.
                existing.need(engine.count() <= len(cpus), 'Workers computed more than one hash each')
                time.sleep(.001)
                continue
            epoch, nonce, digest = row
            existing.need(epoch == EPOCH and nonce in expected and nonce not in seen,
                          'Unexpected epoch, nonce or duplicate share')
            work = bytearray(blob)
            work[40:48] = nonce.to_bytes(8, 'big')
            existing.need(engine.verify(bytes(work), digest), 'Worker digest differs from kernel0 reference')
            seen.add(nonce)
            report['shares'].append({'nonce': nonce, 'digest_hex': digest.hex(), 'reference_verified': True})
        count, dropped = engine.count(), engine.dropped()
        existing.need(seen == expected and count == len(cpus) and dropped == 0 and engine.pop() is None,
                      'Worker count, nonce coverage or queue accounting failed')
        existing.need(existing.verified_bundle(ROOT) == identity, 'Bundle changed during worker qualification')
        report.update(passed=True, completed_hashes=count, dropped_shares=dropped,
                      unique_expected_nonces=len(seen), reference_verified_shares=len(seen))
        print('PASS: %d hugetlb workers; one terminal nonce and reference-verified hash each.' % len(cpus), flush=True)
        return 0
    except (Exception, KeyboardInterrupt) as error:
        report.update(passed=False, error=type(error).__name__ + ': ' + str(error))
        print('WORKER LAYOUT QUALIFICATION STOPPED: ' + report['error'], file=sys.stderr, flush=True)
        return 130 if isinstance(error, KeyboardInterrupt) else 1
    finally:
        try:
            if engine is not None:
                for name in previous:
                    signal.signal(name, signal.SIG_IGN)
                try:
                    engine.pause()
                finally:
                    engine.close()
        except BaseException as error:
            report.update(passed=False, cleanup_error=type(error).__name__ + ': ' + str(error))
            raise
        finally:
            try:
                if lock is not None:
                    os.close(lock)
            finally:
                try:
                    if output is not None:
                        report.update(finished_utc=existing.utc(), elapsed_seconds=time.monotonic() - started)
                        json.dump(report, output, indent=2, allow_nan=False)
                        output.write('\n')
                        output.close()
                finally:
                    for name, handler in previous.items():
                        signal.signal(name, handler)



if __name__ == '__main__':
    raise SystemExit(main())
