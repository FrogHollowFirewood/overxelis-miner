#!/usr/bin/env python3
"""Alternate matched offline samples, loading one native library per fresh process."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import benchmark_native as existing

CHILD_CODE = """import sys
sys.path.insert(0, sys.argv[1])
import benchmark_independent
raise SystemExit(benchmark_independent.child_main())
"""


def text_hash(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def child_main():
    """Trusted child: guard, lock and load only the one requested native DSO."""
    lock = None
    started = time.monotonic()
    try:
        raw = sys.stdin.read(65537)
        existing.need(len(raw) <= 65536, 'Oversized child request')
        request = json.loads(raw)
        existing.need(existing.digest(Path(__file__)) == request['tool_sha256'],
                      'Benchmark tool changed between parent and child')
        existing.platform_check()
        lock = existing.take_lock()
        existing.conflict_check()
        identity = existing.verified_bundle(Path(request['identity']['root']))
        existing.need(identity == request['identity'], 'Bundle identity changed between parent and child')
        cpus = request['cpus']
        existing.need(isinstance(cpus, list) and cpus and all(type(cpu) is int for cpu in cpus),
                      'Invalid child CPU selection')
        checked = existing.topology.select(len(cpus), ','.join(map(str, cpus)))
        existing.need(len(set(cpus)) == len(cpus) and set(checked) == set(cpus), 'Child CPU selection changed')
        # Both loads refer to the same path and therefore the same native DSO.
        # The other comparator is never loaded into this process.
        existing.need(existing.miner.load_native(Path(identity['library'])).nx_selftest() == 0,
                      'Native self-test failed')
        sample = existing.one_run(identity, cpus, request['memory'], request['warmup'],
                                  request['seconds'], existing.miner.KERNELS[request['kernel']])
        existing.need(existing.verified_bundle(Path(identity['root'])) == identity,
                      'Bundle identity changed during sample')
        result = {'passed': True, 'child_pid': os.getpid(), 'identity': identity,
                  'cpus': cpus, 'memory': request['memory'], 'kernel': request['kernel'],
                  'network_used': False, 'miner_libraries_loaded': [identity['library']],
                  'tool_sha256': request['tool_sha256'], 'sample': sample,
                  'child_wall_seconds': time.monotonic() - started}
        print(json.dumps(result, allow_nan=False), flush=True)
        return 0
    except BaseException as error:
        print('CHILD STOPPED: ' + type(error).__name__ + ': ' + str(error), file=sys.stderr, flush=True)
        return 130 if isinstance(error, KeyboardInterrupt) else 1
    finally:
        if lock is not None:
            os.close(lock)


def stop_child(process, grace_seconds=3):
    """Stop and reap this known child; all native workers are its threads."""
    previous = {}
    for name in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        previous[name] = signal.signal(name, signal.SIG_IGN)
    try:
        if process.poll() is None:
            try:
                process.send_signal(signal.SIGINT)
            except ProcessLookupError:
                pass
        try:
            return process.communicate(timeout=grace_seconds)
        except subprocess.TimeoutExpired:
            process.kill()
            return process.communicate(timeout=grace_seconds)
    finally:
        for name, handler in previous.items():
            signal.signal(name, handler)


class ChildInterrupted(KeyboardInterrupt):
    def __init__(self, details):
        super().__init__('Sample interrupted; known child was stopped and reaped')
        self.details = details


class ChildFailure(RuntimeError):
    def __init__(self, message, details):
        super().__init__(message)
        self.details = details


def run_child(request, timeout):
    command = [sys.executable, '-I', '-B', '-c', CHILD_CODE, str(Path(__file__).resolve().parent)]
    request_text = json.dumps(request, separators=(',', ':'), allow_nan=False)
    process = None
    details = {'timeout_seconds': timeout,
               'request_sha256': text_hash(request_text), 'child_code_sha256': text_hash(CHILD_CODE)}
    started = time.monotonic()
    try:
        try:
            controls = {signal.SIGINT, signal.SIGTERM, signal.SIGHUP}
            mask = signal.pthread_sigmask(signal.SIG_BLOCK, controls)
            try:
                # This parent is single-threaded and never loads a native DSO.
                # Commit ownership before a pending control signal can run.
                process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE, text=True, start_new_session=True,
                                           preexec_fn=lambda: signal.pthread_sigmask(signal.SIG_SETMASK, mask))
                details['child_pid'] = process.pid
            finally:
                signal.pthread_sigmask(signal.SIG_SETMASK, mask)
            stdout, stderr = process.communicate(input=request_text, timeout=timeout)
        except (subprocess.TimeoutExpired, KeyboardInterrupt) as error:
            if process is None:
                raise
            stdout, stderr = stop_child(process)
            details.update(returncode=process.returncode, stopped_because=type(error).__name__,
                           stdout_sha256=text_hash(stdout), stderr_sha256=text_hash(stderr),
                           parent_observed_seconds=time.monotonic() - started)
            if isinstance(error, KeyboardInterrupt):
                raise ChildInterrupted(details) from None
            raise ChildFailure('Child sample exceeded its timeout and was reaped', details) from None
        details.update(returncode=process.returncode, stdout_sha256=text_hash(stdout),
                       stderr_sha256=text_hash(stderr), parent_observed_seconds=time.monotonic() - started)
        if process.returncode != 0:
            details['child_error'] = stderr[-4096:]
            raise ChildFailure('Child sample failed', details)
        try:
            result = json.loads(stdout)
        except (ValueError, TypeError):
            raise ChildFailure('Child returned invalid JSON', details) from None
        if not (result.get('passed') is True and result.get('child_pid') == process.pid and
                result.get('identity') == request['identity'] and result.get('cpus') == request['cpus'] and
                result.get('tool_sha256') == request['tool_sha256']):
            raise ChildFailure('Child result identity mismatch', details)
        return result, details
    finally:
        if process is not None and process.poll() is None:
            stop_child(process)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', required=True, type=Path)
    parser.add_argument('--candidate', type=Path, default=ROOT)
    parser.add_argument('--threads', type=int, required=True)
    parser.add_argument('--cpus', help='Optional explicit CPU list, matching --threads')
    parser.add_argument('--memory', choices=sorted(existing.miner.PAGES), default='ordinary')
    parser.add_argument('--kernel', choices=sorted(existing.miner.KERNELS), default='rc1')
    parser.add_argument('--warmup', type=float, default=15)
    parser.add_argument('--seconds', type=float, default=60)
    parser.add_argument('--trials', type=int, default=4)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    if not (math.isfinite(args.seconds) and .25 <= args.seconds <= 3600 and
            math.isfinite(args.warmup) and 0 <= args.warmup <= 600 and 1 <= args.trials <= 20):
        parser.error('seconds: 0.25–3600; warmup: 0–600; trials: 1–20')
    report = {'started_utc': existing.utc(), 'passed': False, 'runs': [],
              'tool_sha256': existing.digest(Path(__file__)), 'child_code_sha256': text_hash(CHILD_CODE),
              'child_code': CHILD_CODE, 'network_used': False, 'synthetic_work': True,
              'measurement': 'Native completed hashes per measured monotonic interval; one DSO per fresh sample process.',
              'order': 'baseline,candidate on odd trials; candidate,baseline on even trials',
              'counter_boundary_note': 'Reads are not simultaneous across workers; each boundary has up to one in-flight hash per worker.',
              'matched_bzminer_comparison': False, 'desktop_target_verified': False,
              'placement_note': 'Comparators never coexist in one process. ASLR, scheduling, temperature, clock and temporal noise still require neutral controls and sustained matched runs.'}
    output = None
    previous_signals = {}
    try:
        def interrupted(*_):
            raise KeyboardInterrupt
        for name in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            previous_signals[name] = signal.signal(name, interrupted)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        output = os.fdopen(os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'w')
        existing.platform_check()
        existing.conflict_check()
        cpus = existing.topology.select(args.threads, args.cpus)
        identities = {'baseline': existing.verified_bundle(args.baseline),
                      'candidate': existing.verified_bundle(args.candidate)}
        report.update(machine=existing.machine_info(), identities=identities, cpus=cpus, threads=len(cpus),
                      memory=args.memory, kernel=args.kernel, warmup_seconds=args.warmup,
                      requested_sample_seconds=args.seconds, trials=args.trials, short_lab_sample=args.seconds < 30)
        # The parent never loads a native DSO or holds the shared lock across
        # children. Each child independently owns the lock during its sample.
        for trial in range(1, args.trials + 1):
            order = ('baseline', 'candidate') if trial % 2 else ('candidate', 'baseline')
            for role in order:
                request = {'identity': identities[role], 'cpus': cpus, 'memory': args.memory,
                           'kernel': args.kernel, 'warmup': args.warmup, 'seconds': args.seconds,
                           'tool_sha256': report['tool_sha256']}
                result, process = run_child(request, args.warmup + args.seconds + 30)
                row = {**result['sample'], 'trial': trial, 'role': role, 'position': len(report['runs']) + 1,
                       'child_result': result, 'process': process}
                report['runs'].append(row)
                print(f"trial {trial} {role}: {row['hashes_per_second'] / 1000:.3f} kH/s | PID {result['child_pid']}", flush=True)
        report.update(passed=True, comparison=existing.compare_pairs(report['runs']))
        return 0
    except (Exception, KeyboardInterrupt) as error:
        report['error'] = type(error).__name__ + ': ' + str(error)
        if isinstance(error, (ChildFailure, ChildInterrupted)):
            report['failed_child'] = error.details
        print('BENCHMARK STOPPED: ' + report['error'], file=sys.stderr, flush=True)
        return 130 if isinstance(error, KeyboardInterrupt) else 1
    finally:
        if output is not None:
            report['finished_utc'] = existing.utc()
            json.dump(report, output, indent=2, allow_nan=False)
            output.write('\n')
            output.close()
        for name, handler in previous_signals.items():
            signal.signal(name, handler)


if __name__ == '__main__':
    raise SystemExit(main())
