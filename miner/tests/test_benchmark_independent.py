"""Accounting, identity and real child cleanup tests; no native miner execution."""
from pathlib import Path
import importlib.util
import json
import os
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / 'tools/benchmark_independent.py'
spec = importlib.util.spec_from_file_location('independent_benchmark_test', PATH)
ind = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ind)
FAKE_CODE = '''import json,os,sys
r=json.load(sys.stdin)
print(json.dumps(dict(passed=True,child_pid=os.getpid(),identity=r['identity'],cpus=r['cpus'],tool_sha256=r['tool_sha256'],sample=dict(counter_start=5,counter_end=25,elapsed_seconds=2,hashes_per_second=10))))
'''
REQUEST = {'identity': {'root':'/fixture','library':'/fixture/build/x.so'},'cpus':[0],
           'memory':'ordinary','warmup':0,'seconds':1,'kernel':'rc1','tool_sha256':'fixture'}


class IndependentProcesses(unittest.TestCase):
    def test_new_child_json_and_raw_accounting_roundtrip(self):
        with patch.object(ind, 'CHILD_CODE', FAKE_CODE):
            result, details = ind.run_child(REQUEST, 5)
        self.assertNotEqual(result['child_pid'], os.getpid())
        self.assertEqual(result['child_pid'], details['child_pid'])
        self.assertEqual(result['sample']['counter_start'], 5)
        self.assertEqual(result['sample']['counter_end'], 25)
        self.assertEqual(result['sample']['hashes_per_second'], 10)
        self.assertEqual(details['returncode'], 0)
        self.assertEqual(details['child_code_sha256'], ind.text_hash(FAKE_CODE))

    def test_altered_child_identity_refused(self):
        code = FAKE_CODE.replace("cpus=r['cpus']", 'cpus=[9999]')
        with patch.object(ind, 'CHILD_CODE', code), self.assertRaises(ind.ChildFailure) as caught:
            ind.run_child(REQUEST, 5)
        self.assertEqual(str(caught.exception), 'Child result identity mismatch')
        self.assertEqual(caught.exception.details['returncode'], 0)

    def test_invalid_child_json_refused(self):
        with patch.object(ind, 'CHILD_CODE', "print('invalid result')"), self.assertRaises(ind.ChildFailure):
            ind.run_child(REQUEST, 5)

    def test_nonzero_child_exit_preserved(self):
        with patch.object(ind, 'CHILD_CODE', 'raise SystemExit(7)'), self.assertRaises(ind.ChildFailure) as caught:
            ind.run_child(REQUEST, 5)
        self.assertEqual(caught.exception.details['returncode'], 7)

    def test_timeout_stops_and_reaps_known_child(self):
        with patch.object(ind, 'CHILD_CODE', 'import time; time.sleep(30)'), self.assertRaises(ind.ChildFailure) as caught:
            ind.run_child(REQUEST, .1)
        details = caught.exception.details
        self.assertEqual(details['stopped_because'], 'TimeoutExpired')
        self.assertIsNotNone(details['returncode'])
        with self.assertRaises(ProcessLookupError):
            os.kill(details['child_pid'], 0)

    def test_parent_interrupt_stops_and_reaps_child(self):
        actual_popen = subprocess.Popen
        children = []
        def interrupting_popen(*args, **kwargs):
            proc = actual_popen(*args, **kwargs)
            children.append(proc)
            actual_communicate = proc.communicate
            first = True
            def communicate(*a, **kw):
                nonlocal first
                if first:
                    first = False
                    raise KeyboardInterrupt
                return actual_communicate(*a, **kw)
            proc.communicate = communicate
            return proc
        with patch.object(ind, 'CHILD_CODE', 'import time; time.sleep(30)'), \
             patch.object(ind.subprocess, 'Popen', interrupting_popen), \
             self.assertRaises(ind.ChildInterrupted) as caught:
            ind.run_child(REQUEST, 5)
        self.assertEqual(caught.exception.details['stopped_because'], 'KeyboardInterrupt')
        self.assertIsNotNone(children[0].poll())
        with self.assertRaises(ProcessLookupError):
            os.kill(children[0].pid, 0)

    def test_sigint_graceful_child_cleanup(self):
        code = "import os,signal,time; signal.signal(signal.SIGINT,lambda *_:os._exit(23)); print('READY',flush=True); time.sleep(30)"
        proc = subprocess.Popen([sys.executable,'-I','-c',code], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,text=True,start_new_session=True)
        self.assertEqual(proc.stdout.readline().strip(), 'READY')
        try:
            ind.stop_child(proc, .2)
            self.assertEqual(proc.returncode, 23)
        finally:
            if proc.poll() is None:
                proc.kill();proc.wait()

    def test_interrupt_at_parent_mask_restore_stops_committed_child(self):
        actual_popen = subprocess.Popen
        actual_sigmask = signal.pthread_sigmask
        parent_pid = os.getpid()
        initial_mask = actual_sigmask(signal.SIG_BLOCK, set())
        children = []
        interrupted = False
        def tracking_popen(*args, **kwargs):
            child = actual_popen(*args, **kwargs)
            children.append(child)
            return child
        def interrupting_restore(how, mask):
            nonlocal interrupted
            previous = actual_sigmask(how, mask)
            if (os.getpid() == parent_pid and how == signal.SIG_SETMASK and
                    children and not interrupted):
                interrupted = True
                raise KeyboardInterrupt
            return previous
        try:
            with patch.object(ind, 'CHILD_CODE', 'import time; time.sleep(30)'), \
                 patch.object(ind.subprocess, 'Popen', tracking_popen), \
                 patch.object(ind.signal, 'pthread_sigmask', interrupting_restore), \
                 self.assertRaises(ind.ChildInterrupted) as caught:
                ind.run_child(REQUEST, .2)
            self.assertTrue(interrupted)
            self.assertEqual(len(children), 1)
            self.assertEqual(caught.exception.details['child_pid'], children[0].pid)
            self.assertEqual(caught.exception.details['stopped_because'], 'KeyboardInterrupt')
            self.assertIsNotNone(children[0].poll())
            with self.assertRaises(ProcessLookupError):
                os.kill(children[0].pid, 0)
        finally:
            actual_sigmask(signal.SIG_SETMASK, initial_mask)
            for child in children:
                if child.poll() is None:
                    child.kill();child.communicate()

    def test_ignored_sigint_is_killed_and_reaped(self):
        code = "import signal,time; signal.signal(signal.SIGINT,signal.SIG_IGN); print('READY',flush=True); time.sleep(30)"
        proc = subprocess.Popen([sys.executable,'-I','-c',code], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,text=True,start_new_session=True)
        self.assertEqual(proc.stdout.readline().strip(), 'READY')
        try:
            ind.stop_child(proc, .03)
            self.assertEqual(proc.returncode, -signal.SIGKILL)
            with self.assertRaises(ProcessLookupError):
                os.kill(proc.pid, 0)
        finally:
            if proc.poll() is None:
                proc.kill();proc.wait()

    def test_pair_comparison_reuses_existing_accounting(self):
        rows=[{'trial':1,'role':'baseline','hashes_per_second':100},
              {'trial':1,'role':'candidate','hashes_per_second':101},
              {'trial':2,'role':'candidate','hashes_per_second':99},
              {'trial':2,'role':'baseline','hashes_per_second':100}]
        result=ind.existing.compare_pairs(rows)
        self.assertAlmostEqual(result['median_paired_gain_percent'],0)
        self.assertEqual(len(result['pairs']),2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
