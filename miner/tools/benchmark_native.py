#!/usr/bin/env python3
"""Matched, finite offline runtime comparison. No pool connections or configuration."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import miner
import topology
from public_common import conflict_check, need, platform_check, take_lock, utc


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verified_bundle(root: Path) -> dict:
    """Require the retained source, exact build, and completed qualification."""
    root = root.resolve(strict=True)
    manifest_path = root / 'SOURCE-MANIFEST.json'
    manifest = json.loads(manifest_path.read_text())
    need(isinstance(manifest.get('files'), dict) and manifest['files'], 'Missing source inventory')
    for name, expected in manifest['files'].items():
        relative = Path(name)
        source = root / relative
        need(not relative.is_absolute() and '..' not in relative.parts and
             source.is_file() and not source.is_symlink() and
             source.resolve().is_relative_to(root), 'Unsafe or missing source entry: ' + name)
        need(digest(source) == expected, 'Source checksum mismatch: ' + name)
    build = json.loads((root / 'build/build.json').read_text())
    qualified = json.loads((root / 'evidence/kernel-qualification.json').read_text())
    library = root / 'build/liboverxelis.so'
    need(library.is_file() and not library.is_symlink(), 'Missing or unsafe compiled library')
    actual = digest(library)
    need(build.get('status') == 'built_pending_qualification' and
         build.get('source_manifest_sha256') == digest(manifest_path) and
         build.get('library_sha256') == actual and
         qualified.get('passed') is True and
         qualified.get('library_sha256') == actual and qualified.get('cases') == 1031,
         'Build/qualification identity mismatch; build and qualify each source tree first')
    return {'root': str(root), 'version': manifest.get('version'), 'edition': manifest.get('edition'),
            'library': str(library), 'library_sha256': actual,
            'source_manifest_sha256': digest(manifest_path),
            'compiler': build.get('compiler'), 'cpu_info_at_build': build.get('cpu_info')}


def count_sample(engine, clock=time.monotonic_ns):
    before = clock()
    count = engine.count()
    after = clock()
    # The native aggregate reads one counter per worker. Record its duration;
    # the midpoint is an estimate, not an atomic snapshot of all workers.
    return count, (before + after) / 2 / 1e9, (after - before) / 1e9


def sample(engine, seconds, clock=time.monotonic_ns, sleeper=time.sleep):
    count0, time0, read0 = count_sample(engine, clock)
    sleeper(seconds)
    count1, time1, read1 = count_sample(engine, clock)
    elapsed = time1 - time0
    need(elapsed > 0 and count1 >= count0, 'Invalid native counter interval')
    return {'completed_hashes': count1 - count0, 'elapsed_seconds': elapsed,
            'hashes_per_second': (count1 - count0) / elapsed,
            'counter_start': count0, 'counter_end': count1,
            'counter_read_seconds': [read0, read1]}


def one_run(identity, cpus, page_mode, warmup, seconds, kernel):
    engine = miner.NativeEngine(cpus, kernel, miner.PAGES[page_mode], Path(identity['library']))
    try:
        need(engine.pages() == (len(cpus) if page_mode == 'hugetlb' else 0),
             'Requested memory mode unavailable; comparison refused')
        # Deterministic synthetic work, with a zero target: no normal shares,
        # transport, fee scheduling, or pool variance enters this throughput test.
        blob = bytes((i * 173 + 91) & 255 for i in range(112))
        engine.set_job(blob, bytes(32), 1, 0)
        time.sleep(warmup)
        measured = sample(engine, seconds)
        measured.update(huge_page_workers=engine.pages(), dropped_shares=engine.dropped())
        need(measured['completed_hashes'] > 0 and measured['dropped_shares'] == 0,
             'No work completed or unexpected dropped shares')
        return measured
    finally:
        engine.pause()
        engine.close()


def compare_pairs(rows):
    by_trial = {}
    for row in rows:
        by_trial.setdefault(row['trial'], {})[row['role']] = row['hashes_per_second']
    pairs = []
    for trial, rates in sorted(by_trial.items()):
        if set(rates) == {'baseline', 'candidate'}:
            pairs.append({'trial': trial, 'candidate_over_baseline_percent':
                          (rates['candidate'] / rates['baseline'] - 1) * 100})
    if not pairs:
        return {'pairs': []}
    changes = [p['candidate_over_baseline_percent'] for p in pairs]
    return {'pairs': pairs, 'median_paired_gain_percent': statistics.median(changes),
            'min_paired_gain_percent': min(changes), 'max_paired_gain_percent': max(changes),
            'meaning': 'Local gross completed-hash throughput; no pool-accepted work, payout, or statistical confidence claim.'}


def machine_info():
    cpu_lines = Path('/proc/cpuinfo').read_text().splitlines()
    model = next((line.split(':', 1)[1].strip() for line in cpu_lines if line.startswith('model name')), 'unknown')
    try:
        quota = Path('/sys/fs/cgroup/cpu.max').read_text().strip()
    except OSError:
        quota = None
    return {'cpu_model': model, 'platform': platform.platform(), 'python': platform.python_version(),
            'allowed_cpus': sorted(os.sched_getaffinity(0)), 'cgroup_cpu_max': quota,
            'power_thermal_and_clock_conditions_measured': False,
            'conditions_note': 'Record target power, thermals, clocks, memory, huge-page setup and background workload separately.'}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline', required=True, type=Path, help='Built and qualified beta.2 source tree')
    p.add_argument('--candidate', type=Path, default=ROOT, help='Built and qualified candidate source tree')
    p.add_argument('--threads', type=int, required=True, help='Explicit worker count; e.g. 192 on the 7995WX')
    p.add_argument('--cpus', help='Optional explicit CPU list; must match --threads')
    p.add_argument('--memory', choices=sorted(miner.PAGES), default='ordinary')
    p.add_argument('--kernel', choices=sorted(miner.KERNELS), default='rc1')
    p.add_argument('--warmup', type=float, default=10)
    p.add_argument('--seconds', type=float, default=60)
    p.add_argument('--trials', type=int, default=4, help='Each trial measures both builds; order alternates')
    p.add_argument('--output', type=Path, required=True, help='New JSON report; existing output is never replaced')
    a = p.parse_args(argv)
    if not (math.isfinite(a.seconds) and .25 <= a.seconds <= 3600 and
            math.isfinite(a.warmup) and 0 <= a.warmup <= 600 and 1 <= a.trials <= 20):
        p.error('seconds: 0.25–3600; warmup: 0–600; trials: 1–20')
    report = {'started_utc': utc(), 'passed': False, 'runs': [],
              'network_used': False, 'synthetic_work': True, 'target': 'zero',
              'measurement': 'Completed native hashes divided by measured monotonic elapsed time.',
              'counter_boundary_note': 'Counter reads are not simultaneous across workers. Each boundary also has up to one in-flight hash per worker; use sustained samples.',
              'matched_bzminer_comparison': False, 'desktop_target_verified': False}
    lock = output = None
    try:
        platform_check()
        lock = take_lock()
        conflict_check()
        cpus = topology.select(a.threads, a.cpus)
        identities = {'baseline': verified_bundle(a.baseline), 'candidate': verified_bundle(a.candidate)}
        report.update(machine=machine_info(), identities=identities, cpus=cpus,
                      threads=len(cpus), memory=a.memory, kernel=a.kernel,
                      warmup_seconds=a.warmup, requested_sample_seconds=a.seconds, trials=a.trials,
                      short_lab_sample=a.seconds < 30)
        # Reserve report before loading code; refuses symlinks and accidental overwrite.
        a.output.parent.mkdir(parents=True, exist_ok=True)
        output = os.fdopen(os.open(a.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'w')
        for identity in identities.values():
            need(miner.load_native(Path(identity['library'])).nx_selftest() == 0, 'Native self-test failed')
        for trial in range(1, a.trials + 1):
            order = ('baseline', 'candidate') if trial % 2 else ('candidate', 'baseline')
            for role in order:
                row = one_run(identities[role], cpus, a.memory, a.warmup, a.seconds, miner.KERNELS[a.kernel])
                row.update(trial=trial, role=role, position=len(report['runs']) + 1)
                report['runs'].append(row)
                print(f"trial {trial} {role}: {row['hashes_per_second'] / 1000:.3f} kH/s", flush=True)
        report.update(passed=True, comparison=compare_pairs(report['runs']))
        return 0
    except (Exception, KeyboardInterrupt) as error:
        report['error'] = type(error).__name__ + ': ' + str(error)
        print('BENCHMARK STOPPED: ' + report['error'], file=sys.stderr)
        return 130 if isinstance(error, KeyboardInterrupt) else 1
    finally:
        if output is not None:
            report['finished_utc'] = utc()
            json.dump(report, output, indent=2, allow_nan=False)
            output.write('\n')
            output.close()
        if lock is not None:
            os.close(lock)


if __name__ == '__main__':
    raise SystemExit(main())
