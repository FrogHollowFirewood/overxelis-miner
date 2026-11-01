"""Offline protocol and lifetime nonce regressions; no native work or network."""
from pathlib import Path
import json
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import miner
import overxelis_fee as fee

CONFIG = {"pool": "stratum+tcp://pool.invalid:1234", "wallet": "xel:test",
          "worker": "test-worker", "password": "x"}


class Engine:
    def __init__(self):
        self.active = False
        self.queue = []
        self.jobs = []
        self.valid = True
    def set_job(self, blob, target, epoch, start):
        self.active = True
        self.jobs.append((blob, target, epoch, start))
    def pause(self):
        self.active = False
        self.queue.clear()
    def pop(self):
        return self.queue.pop(0) if self.queue else None
    def verify(self, work, digest):
        return self.valid


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.engine, self.sent = Engine(), []
        self.now = 0.0
        self.tracker = miner.NonceTracker(192, 1000)
        self.session = miner.Session(self.engine, CONFIG, self.sent.append,
                                     clock=lambda: self.now, nonce_start=1000,
                                     seen=self.tracker)
        self.session.start()
    def reply(self, kind):
        ident = next(k for k, v in self.session.pending.items() if v.kind == kind)
        result = ["session", "12", 1, "34" * 32] if kind == "subscribe" else True
        self.session.handle({"id": ident, "result": result})
    def notify(self, label="job", clean=True, header="56"):
        self.session.handle({"method": "mining.notify",
                             "params": [label, "1234", header * 32, "xel/v3", clean]})
    def ready(self):
        self.reply("subscribe")
        self.reply("authorize")
        self.session.handle({"method": "mining.set_difficulty", "params": [1]})
        self.notify()
    def submit(self, nonce):
        self.engine.queue.append((self.session.active.epoch, nonce, bytes(32)))
        self.session.drain()
    def test_pipelined_job_waits_for_both_handshake_replies(self):
        self.session.handle({"method": "mining.set_difficulty", "params": [1]})
        self.notify()
        self.assertFalse(self.engine.active)
        self.reply("authorize")
        self.assertFalse(self.engine.active)
        self.reply("subscribe")
        self.assertTrue(self.engine.active)
        self.assertEqual(len(self.engine.jobs), 1)
    def test_replay_is_suppressed_after_same_header_new_label(self):
        self.ready(); self.submit(1000)
        self.notify("replacement")
        self.submit(1000)
        self.assertEqual(self.session.stats.submitted, 1)
        self.assertEqual(self.session.stats.duplicates_local, 1)
    def test_replay_is_suppressed_after_changed_header(self):
        self.ready(); self.submit(1000)
        self.notify("replacement", header="78")
        self.submit(1000)
        self.assertEqual(self.session.stats.submitted, 1)
        self.assertEqual(self.session.stats.duplicates_local, 1)
    def test_replay_protection_survives_reconnect(self):
        self.ready(); self.submit(1000); self.session.disconnect()
        next_epoch = self.session.next_epoch
        self.session = miner.Session(self.engine, CONFIG, self.sent.append,
                                     clock=lambda: self.now, nonce_start=1000,
                                     seen=self.tracker, epoch_start=next_epoch)
        self.session.start(); self.ready(); self.submit(1000); self.submit(1192)
        self.assertEqual(self.session.stats.submitted, 1)
        self.assertEqual(self.session.stats.duplicates_local, 1)
    def test_lower_nonce_from_same_stream_is_suppressed(self):
        self.ready(); self.submit(1384); self.submit(1192)
        self.assertEqual(self.session.stats.submitted, 1)
        self.assertEqual(self.session.stats.duplicates_local, 1)
    def test_streams_may_be_consumed_in_any_interleaving(self):
        self.ready()
        for nonce in (1577, 1000, 1385, 1192):
            self.submit(nonce)
        self.assertEqual(self.session.stats.submitted, 3)
        self.assertEqual(self.session.stats.duplicates_local, 1)
    def test_nonce_before_search_start_stops(self):
        self.ready()
        with self.assertRaises(miner.VerificationError): self.submit(999)
        self.assertFalse(self.engine.active)
        self.assertEqual(self.session.stats.invalid_local, 1)
        self.assertEqual(self.session.stats.submitted, 0)
    def test_reference_failure_is_not_recorded_as_submitted(self):
        self.ready(); self.engine.valid = False
        with self.assertRaises(miner.VerificationError): self.submit(1000)
        self.assertEqual(self.tracker.high_water, [None] * 192)
        self.assertFalse(self.engine.active)
    def test_late_stale_rejection_does_not_pause_replacement(self):
        self.ready(); self.submit(1000)
        ident = next(k for k, v in self.session.pending.items() if v.kind == "submit")
        self.notify("replacement", clean=False)
        self.session.handle({"id": ident, "error": [21, "stale"]})
        self.assertTrue(self.engine.active)
        self.assertFalse(self.session.wait_notify)
    def test_pending_share_timeout_counts_once(self):
        self.ready(); self.submit(1000)
        self.now = 31; self.session.expire(); self.session.expire()
        self.assertEqual(self.session.stats.unresolved, 1)
        self.assertEqual(self.session.stats.unresolved_work, 1)
    def test_long_session_crosses_old_limit_without_growth(self):
        self.ready()
        for nonce in range(1000, 1000 + 33000):
            self.submit(nonce)
            ident = next(k for k, v in self.session.pending.items() if v.kind == "submit")
            self.session.handle({"id": ident, "result": True})
        self.assertEqual(self.session.stats.accepted, 33000)
        self.assertEqual(len(self.tracker.high_water), 192)
        self.assertTrue(self.engine.active)
    def test_legacy_injected_set_keeps_fail_closed_capacity(self):
        self.session.seen = set()
        self.session.max_seen = 1
        self.ready(); self.submit(1000)
        with self.assertRaises(miner.CacheFull): self.submit(1192)
        self.assertFalse(self.engine.active)


class NonceTrackerTests(unittest.TestCase):
    def test_invalid_arguments(self):
        for threads, start in ((0, 0), (1025, 0), (True, 0), (192, -1),
                               (192, 1 << 64), (192, True)):
            with self.assertRaises(ValueError): miner.NonceTracker(threads, start)
    def test_one_watermark_per_worker_at_192_threads(self):
        tracker = miner.NonceTracker(192, 17)
        for worker in reversed(range(192)):
            for step in range(200):
                self.assertTrue(tracker.claim(17 + worker + 192 * step))
        for worker in range(192):
            self.assertFalse(tracker.claim(17 + worker))
        self.assertEqual(len(tracker.high_water), 192)
    def test_worker_gaps_and_unequal_progress_do_not_reject_other_workers(self):
        tracker = miner.NonceTracker(192, 99991)
        self.assertTrue(tracker.claim(99991 + 191 + 192 * 10000))
        self.assertTrue(tracker.claim(99991))
        self.assertTrue(tracker.claim(99991 + 77 + 192 * 3))
        self.assertTrue(tracker.claim(99991 + 77 + 192 * 99))
        self.assertTrue(tracker.claim(99991 + 192))
        self.assertFalse(tracker.claim(99991 + 77 + 192 * 4))
    def test_last_uint64_nonce_is_valid_without_wrap(self):
        tracker = miner.NonceTracker(192, (1 << 64) - 100)
        self.assertTrue(tracker.claim((1 << 64) - 1))
        self.assertFalse(tracker.claim((1 << 64) - 1))
        with self.assertRaises(miner.VerificationError): tracker.claim(1 << 64)
    def test_non_native_engine_uses_legacy_set(self):
        self.assertIsInstance(miner.duplicate_tracker(Engine(), 0), set)
    def test_native_contract_selects_bounded_tracker(self):
        engine = Engine(); engine.threads = 192
        self.assertIsInstance(miner.duplicate_tracker(engine, 0), miner.NonceTracker)


class FeeTrackerTests(unittest.TestCase):
    def test_one_tracker_spans_user_fee_and_resumed_user(self):
        # Reuse the deterministic transport fixture; this engine declares the
        # native nonce contract, then injects a replay in both later phases.
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from test_overxelis_fee import World
        world = World()
        world.engine.threads = 192
        original_set_job = world.engine.set_job
        def inject_replay(blob, target, epoch, start):
            original_set_job(blob, target, epoch, start)
            if epoch > 1:
                world.engine.queue.append((epoch, start + 1, bytes(32)))
        world.engine.set_job = inject_replay
        with patch.object(miner, "duplicate_tracker", wraps=miner.duplicate_tracker) as factory:
            result = world.run(102)
        factory.assert_called_once_with(world.engine, world.engine.jobs[0][2])
        self.assertEqual([role for role, *_ in world.calls], ["USER", "FEE", "USER"])
        self.assertEqual(result["user_stats"]["duplicates_local"], 1)
        self.assertEqual(result["fee_stats"]["duplicates_local"], 1)
        self.assertEqual(result["user_stats"]["accepted"], 2)
        self.assertEqual(result["fee_stats"]["accepted"], 1)


class FrameTests(unittest.TestCase):
    def test_split_frame_and_multiple_frames_preserve_order(self):
        frames = miner.Frames()
        first = json.dumps({"id": 1, "result": True}).encode() + b"\n"
        second = json.dumps({"id": 2, "result": False}).encode() + b"\n"
        self.assertEqual(frames.feed(first[:8]), [])
        self.assertEqual(frames.feed(first[8:] + second),
                         [{"id": 1, "result": True}, {"id": 2, "result": False}])
    def test_oversized_or_nonobject_frame_rejected(self):
        for data in (b"[]\n", b"{\"x\":NaN}\n", b"x" * 9):
            with self.assertRaises(miner.ProtocolError): miner.Frames(limit=8).feed(data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
