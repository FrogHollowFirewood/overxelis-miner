"""Native worker state-machine tests using deliberately NON-consensus hash stubs.

These tests compile only the worker runtime plus a 1 ms synthetic hash function.
They do not qualify XelisHash or load the production shared library.
"""
from pathlib import Path
import ctypes as C
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import miner

STUB = r'''
#include <stdint.h>
#include <string.h>
#include <unistd.h>
#include <pthread.h>
static pthread_mutex_t gate_mutex = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t gate_wake = PTHREAD_COND_INITIALIZER;
static int gated = 0;
static unsigned tokens = 0;
void stub_gate(int enabled) {
    pthread_mutex_lock(&gate_mutex);
    gated = enabled;
    pthread_cond_broadcast(&gate_wake);
    pthread_mutex_unlock(&gate_mutex);
}
void stub_release(unsigned count) {
    pthread_mutex_lock(&gate_mutex);
    tokens += count;
    pthread_cond_broadcast(&gate_wake);
    pthread_mutex_unlock(&gate_mutex);
}
void chacha_init(void) {}
void xelis_hash_v3(uint8_t *blob, uint8_t *hash, uint64_t *scratch) {
    (void)scratch;
    pthread_mutex_lock(&gate_mutex);
    while (gated && tokens == 0) pthread_cond_wait(&gate_wake, &gate_mutex);
    if (gated) --tokens;
    pthread_mutex_unlock(&gate_mutex);
    usleep(1000);
    memset(hash, 0, 32);
    memcpy(hash, blob + 40, 8);
}
void xelis_hash_v3_opt(uint8_t *b, uint8_t *h, uint64_t *s) { xelis_hash_v3(b,h,s); }
void xelis_hash_v3_experimental(uint8_t *b, uint8_t *h, uint64_t *s) { xelis_hash_v3(b,h,s); }
void xelis_hash_v3_exp_sqrt(uint8_t *b, uint8_t *h, uint64_t *s) { xelis_hash_v3(b,h,s); }
'''
MAX = (1 << 64) - 1


class WorkerState(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if platform.system() != 'Linux' or platform.machine() != 'x86_64' or not shutil.which('gcc'):
            raise unittest.SkipTest('Linux x86-64 and GCC required for runtime stub tests')
        if 'aes' not in Path('/proc/cpuinfo').read_text().split():
            raise unittest.SkipTest('runtime requires AES-capable CPU')
        cls.temp = tempfile.TemporaryDirectory()
        directory = Path(cls.temp.name)
        source = directory / 'stub.c'
        source.write_text(STUB)
        cls.library = directory / 'runtime-stub.so'
        subprocess.run(['gcc', '-O2', '-std=gnu11', '-shared', '-fPIC', '-pthread',
                        '-I' + str(ROOT / 'include'), str(ROOT / 'experiments/runtime-topology-colored-huge.c'),
                        str(source), '-Wl,--no-undefined', '-o', str(cls.library)],
                       check=True, capture_output=True, text=True, timeout=30)
        cls.cpus = sorted(os.sched_getaffinity(0))[:4]

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'temp'):
            cls.temp.cleanup()

    def engine(self, threads):
        engine = miner.NativeEngine(self.cpus[:threads], 1, 0, self.library)
        self.addCleanup(engine.close)
        return engine

    def wait_count(self, engine, count):
        end = time.monotonic() + 3
        while engine.count() < count and time.monotonic() < end:
            time.sleep(.001)
        self.assertEqual(engine.count(), count)

    def drain(self, engine):
        rows = []
        while True:
            row = engine.pop()
            if row is None:
                return rows
            rows.append(row)

    def wait_shares(self, engine, count):
        # nx_count publishes before the worker enqueues its share. Wait for the
        # separately published queue rather than assuming those events coincide.
        rows = []
        end = time.monotonic() + 3
        while len(rows) < count and time.monotonic() < end:
            rows.extend(self.drain(engine))
            if len(rows) < count:
                time.sleep(.001)
        self.assertEqual(len(rows), count)
        return rows

    def test_exhaustion_never_wraps_and_workers_partition_nonce_space(self):
        n = min(3, len(self.cpus))
        engine = self.engine(n)
        engine.set_job(bytes(112), bytes([255]) * 32, 7, MAX - 11)
        self.wait_count(engine, 12)
        rows = self.wait_shares(engine, 12)
        self.assertEqual({row[1] for row in rows}, set(range(MAX - 11, MAX + 1)))
        self.assertEqual(len(rows), 12)
        self.assertTrue(all(epoch == 7 and int.from_bytes(digest[:8], 'big') == nonce
                            for epoch, nonce, digest in rows))
        time.sleep(.01)
        self.assertEqual(engine.count(), 12)

    def test_initial_nonce_overflow_parks_only_out_of_range_workers(self):
        if len(self.cpus) < 3:
            self.skipTest('three allowed CPUs required')
        engine = self.engine(min(4, len(self.cpus)))
        engine.set_job(bytes(112), bytes([255]) * 32, 7, MAX - 1)
        self.wait_count(engine, 2)
        rows = self.wait_shares(engine, 2)
        self.assertEqual(sorted(row[1] for row in rows), [MAX - 1, MAX])

    def test_pause_invalidates_queued_share_and_later_job_does_not_reset_nonce(self):
        engine = self.engine(1)
        engine.set_job(bytes(112), bytes([255]) * 32, 7, MAX)
        self.wait_count(engine, 1)
        engine.pause()
        self.assertIsNone(engine.pop())
        engine.set_job(bytes(112), bytes([255]) * 32, 8, 0)
        time.sleep(.015)
        self.assertEqual(engine.count(), 1)
        self.assertIsNone(engine.pop())

    def test_each_fixed_stride_stream_increases_across_pause_and_job_change(self):
        n = min(3, len(self.cpus))
        engine = self.engine(n)
        engine.lib.stub_gate.argtypes = [C.c_int]
        engine.lib.stub_gate.restype = None
        engine.lib.stub_release.argtypes = [C.c_uint]
        engine.lib.stub_release.restype = None
        engine.lib.stub_gate(1)
        # Cleanup releases any worker still inside the deliberately gated stub
        # before the runtime joins its threads.
        self.addCleanup(engine.lib.stub_gate, 0)
        start = MAX - 95
        engine.set_job(bytes(112), bytes([255]) * 32, 7, start)
        engine.lib.stub_release(6)
        self.wait_count(engine, 6)
        first = self.wait_shares(engine, 6)
        self.assertEqual(len(first), 6)
        engine.pause()
        self.assertIsNone(engine.pop())
        engine.set_job(bytes(range(112)), bytes([255]) * 32, 8, 0)
        engine.lib.stub_release(96)
        self.wait_count(engine, 96)
        later = self.drain(engine)
        self.assertTrue(later)
        self.assertTrue(all(epoch == 8 for epoch, _, _ in later))
        high = {}
        for _, nonce, _ in first + later:
            residue = (nonce - start) % n
            if residue in high:
                self.assertGreater(nonce, high[residue])
            high[residue] = nonce
        self.assertEqual(set(high), set(range(n)))
        self.assertEqual(len({nonce for _, nonce, _ in first + later}), len(first + later))
        self.assertEqual(engine.dropped(), 0)

    def test_job_update_discards_old_queue_and_never_replays_consumed_nonce(self):
        engine = self.engine(1)
        engine.set_job(bytes(112), bytes([255]) * 32, 7, MAX - 31)
        end = time.monotonic() + 3
        while engine.count() < 2 and time.monotonic() < end:
            time.sleep(.001)
        self.assertGreaterEqual(engine.count(), 2)
        engine.set_job(bytes(range(112)), bytes([255]) * 32, 8, 0)
        self.wait_count(engine, 32)
        rows = self.drain(engine)
        self.assertTrue(rows)
        self.assertTrue(all(epoch == 8 for epoch, _, _ in rows))
        nonces = [row[1] for row in rows]
        self.assertEqual(len(nonces), len(set(nonces)))
        self.assertTrue(all(MAX - 29 <= nonce <= MAX for nonce in nonces))


if __name__ == '__main__':
    unittest.main(verbosity=2)
