"""Offline beta.2 tests. Fake engines never invoke native hashing or a public pool."""
import copy
import json
from pathlib import Path
import socket
import sys
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import miner
import overxelis_fee as fee

USER = {"pool": "stratum+tcp://user.invalid:1234", "wallet": "xel:TEST_USER_ONLY", "worker": "test-user", "password": "user-private-password"}


class Clock:
    def __init__(self): self.value = 0.0
    def __call__(self): return self.value
    def advance(self, seconds): self.value += seconds


class Engine:
    def __init__(self):
        self.queue, self.jobs = [], []
        self.active, self.total, self.reads, self.drop = False, 0, 0, 0
        self.valid = True
    def set_job(self, blob, target, epoch, nonce):
        self.active = True
        self.jobs.append((blob, epoch, nonce))
        self.queue = [(epoch, nonce + epoch, bytes(32))]
    def pause(self): self.active = False; self.queue.clear()
    def pop(self): return self.queue.pop(0) if self.queue else None
    def count(self): self.reads += 1; return self.total
    def dropped(self): return self.drop
    def verify(self, work, digest): return self.valid
    def pages(self): return 192


class FakeTimer:
    def __init__(self, seconds, callback): self.seconds, self.callback, self.daemon = seconds, callback, False
    def start(self): pass
    def cancel(self): pass
    def join(self, timeout=None): pass
    def is_alive(self): return False


class Connection:
    def __init__(self, world, role, reject_auth=False):
        self.world, self.role, self.reject_auth = world, role, reject_auth
        self.frames, self.closed = [], False
        self.submissions = []
    def settimeout(self, timeout): self.timeout = timeout
    def sendall(self, data):
        m = json.loads(data)
        self.world.messages.append((self.role, m))
        kind, ident = m.get("method"), m.get("id")
        if kind == "mining.subscribe":
            self.frames.append({"id": ident, "result": ["session", "a1", 1, ("34" if self.role == "USER" else "45") * 32]})
        elif kind == "mining.authorize":
            self.frames.append({"id": ident, "result": not self.reject_auth})
            self.frames += [
                {"method": "mining.set_difficulty", "params": [1]},
                {"method": "mining.notify", "params": ["job-" + str(len(self.world.connections)), "1234", "56" * 32, "xel/v3", True]}]
        elif kind == "mining.submit":
            self.submissions.append(m)
            self.frames.append({"id": ident, "result": self.role not in self.world.reject_shares})
    def recv(self, size):
        self.world.clock.advance(0.05)
        self.world.engine.total += 10 if self.world.engine.active else 0
        if self.frames:
            data = b"".join(json.dumps(x).encode() + b"\n" for x in self.frames)
            self.frames = []
            return data
        raise socket.timeout()
    def close(self): self.closed = True


class World:
    def __init__(self):
        self.clock, self.engine = Clock(), Engine()
        self.connections, self.messages, self.calls, self.logs = [], [], [], []
        self.fail_fee = self.bad_fee_auth = self.bad_user_auth = False
        self.user_failures = 0
        self.reject_shares = set()
        self.connect_delay = 0.0
    def connector(self, role):
        def connect(config, timeout):
            self.calls.append((role, self.clock(), dict(config)))
            if role == "FEE" and self.fail_fee:
                raise OSError("simulated unavailable pool")
            if role == "USER" and self.user_failures:
                self.user_failures -= 1
                raise OSError("simulated user failure")
            self.clock.advance(self.connect_delay)
            connection = Connection(self, role, self.bad_fee_auth if role == "FEE" else self.bad_user_auth)
            self.connections.append(connection)
            return connection
        return connect
    def run(self, duration=102.0):
        self.display = fee.FeeDisplay(self.engine, self.logs.append, 10, self.clock)
        self.result = fee.run_pool(self.engine, USER, duration, self.display, policy=fee.Policy(99, 1),
                                  clock=self.clock, sleep=self.clock.advance,
                                  connectors={r: self.connector(r) for r in ("USER", "FEE")}, timer_factory=FakeTimer, standby_factory=None)
        return self.result


class PolicyTests(unittest.TestCase):
    def test_production_ratio(self):
        p = fee.Policy()
        self.assertEqual((p.user_seconds, p.fee_seconds), (5940, 60))
        self.assertEqual(p.fee_seconds / (p.user_seconds + p.fee_seconds), 0.01)
    def test_reject_overcharge(self):
        for values in ((90, 10), (0, 0), (-1, 1), (float("nan"), 1), (float("inf"), 1), (99, float("inf"))):
            with self.assertRaises(ValueError): fee.Policy(*values)
    def test_fee_destination_and_no_credential_reuse(self):
        before = copy.deepcopy(USER)
        c = fee.fee_config(USER)
        self.assertEqual(c["wallet"], fee.FEE_WALLET)
        self.assertEqual(c["pool"], fee.FEE_POOL)
        self.assertEqual(c["password"], "x")
        self.assertNotEqual(c["worker"], USER["worker"])
        self.assertEqual(USER, before)


class GateTests(unittest.TestCase):
    def setUp(self): self.clock, self.native = Clock(), Engine(); self.g = fee.MeteredEngine(self.native, self.clock)
    def start(self): self.g.set_job(bytes(112), bytes(32), 1, 0)
    def test_idle_time_not_credited(self):
        self.clock.advance(100); self.assertEqual(self.g.active_seconds("USER"), 0)
    def test_active_pause_accounting(self):
        self.start(); self.clock.advance(12); self.g.pause(); self.clock.advance(30); self.g.pause()
        self.assertEqual(self.g.active_seconds("USER"), 12)
        self.assertEqual(self.g.active_seconds("FEE"), 0)
    def test_must_pause_before_role_change(self):
        self.start()
        with self.assertRaises(RuntimeError): self.g.set_phase("FEE", 60)
    def test_expired_job_never_starts(self):
        self.g.set_phase("FEE", 1); self.clock.advance(1)
        with self.assertRaises(fee.PhaseEnded): self.start()
        self.assertFalse(self.native.active)
    def test_seal_stops_and_blocks_late_job(self):
        self.g.set_phase("FEE", 60); self.start(); self.clock.advance(3); self.g.seal()
        with self.assertRaises(fee.PhaseEnded): self.start()
        self.assertFalse(self.native.active)
        self.assertEqual(self.g.active_seconds("FEE"), 3)
    def test_real_watchdog(self):
        g = fee.MeteredEngine(self.native)
        g.set_phase("FEE", time.monotonic() + 0.05)
        g.set_job(bytes(112), bytes(32), 1, 0)
        timer = threading.Timer(0.05, g.seal); timer.start(); timer.join(1)
        self.assertFalse(timer.is_alive()); self.assertFalse(self.native.active); self.assertTrue(g.sealed)
    def test_reconnect_preserves_credit(self):
        self.start(); self.clock.advance(12); self.g.pause(); self.clock.advance(20); self.start(); self.clock.advance(4)
        self.assertEqual(self.g.active_seconds("USER"), 16)


class DisplayTests(unittest.TestCase):
    def test_exactly_one_counter_read(self):
        c, e, logs = Clock(), Engine(), []
        d = fee.FeeDisplay(e, logs.append, 1, c)
        self.assertEqual(e.reads, 1)
        c.advance(1); e.total = 1000; d.report(True)
        self.assertEqual(e.reads, 2)
        self.assertIn("Local: 1.000 kH/s", logs[-1])
    def test_regression_stops(self):
        c, e = Clock(), Engine(); e.total = 5
        d = fee.FeeDisplay(e, lambda x: None, 1, c); e.total = 0
        with self.assertRaises(RuntimeError): d.report(force=True)
    def test_queue_overflow_stops(self):
        c, e = Clock(), Engine(); e.drop = 1
        d = fee.FeeDisplay(e, lambda x: None, 1, c)
        with self.assertRaises(RuntimeError): d.report(force=True)


class SwitchingTests(unittest.TestCase):
    def test_no_startup_fee(self):
        w = World(); r = w.run(50)
        self.assertEqual(r["fee_windows"], 0)
        self.assertTrue(all(c[0] == "USER" for c in w.calls))
    def test_full_cycle_returns_to_user(self):
        w = World(); r = w.run(102)
        self.assertEqual([c[0] for c in w.calls], ["USER", "FEE", "USER"])
        self.assertEqual(r["fee_windows"], 1)
        self.assertGreaterEqual(r["user_active_seconds"], 99)
        self.assertLessEqual(r["fee_active_seconds"], 1.000001)
        self.assertGreaterEqual(r["user_stats"]["accepted"], 2)
        self.assertGreaterEqual(r["fee_stats"]["accepted"], 1)
        self.assertTrue(all(c.closed for c in w.connections)); self.assertFalse(w.engine.active)
    def test_wallet_and_worker_routing(self):
        w = World(); w.run(102)
        for role, m in w.messages:
            if m.get("method") == "mining.authorize":
                self.assertEqual(m["params"][0], USER["wallet"] if role == "USER" else fee.FEE_WALLET)
            if m.get("method") == "mining.submit":
                self.assertEqual(m["params"][0], USER["worker"] if role == "USER" else fee.fee_config(USER)["worker"])
    def test_epoch_increases_across_wallet_switches(self):
        w = World(); w.run(102)
        epochs = [x[1] for x in w.engine.jobs]
        self.assertEqual(epochs, sorted(set(epochs)))
        self.assertGreaterEqual(len(epochs), 3)
    def test_fee_connection_failure_skips_without_catchup(self):
        w = World(); w.fail_fee = True; r = w.run(120)
        self.assertEqual(r["fee_windows"], 1)
        self.assertEqual(r["skipped_fee_windows"], 1)
        self.assertEqual(r["fee_active_seconds"], 0)
        self.assertEqual([c[0] for c in w.calls], ["USER", "FEE", "USER"])
    def test_fee_authorization_failure_returns_user(self):
        w = World(); w.bad_fee_auth = True; r = w.run(120)
        self.assertEqual(r["skipped_fee_windows"], 1)
        self.assertEqual(r["fee_active_seconds"], 0)
        self.assertEqual([c[0] for c in w.calls], ["USER", "FEE", "USER"])
    def test_user_authorization_failure_is_fatal(self):
        w = World(); w.bad_user_auth = True
        with self.assertRaises(miner.AuthorizationError): w.run()
        self.assertFalse(w.engine.active); self.assertTrue(all(c.closed for c in w.connections))
    def test_user_outage_does_not_earn_fee(self):
        w = World(); w.user_failures = 3; r = w.run(102)
        self.assertEqual(r["fee_windows"], 0)
        self.assertEqual(r["user_stats"]["reconnects"], 3)
    def test_connection_time_does_not_earn_fee(self):
        w = World(); w.connect_delay = 5; r = w.run(102)
        self.assertEqual(r["fee_windows"], 0)
    def test_slow_fee_connection_cannot_start_late_hashing(self):
        w = World(); w.connect_delay = 2; r = w.run(105)
        self.assertEqual(r["fee_windows"], 1); self.assertEqual(r["fee_active_seconds"], 0)
        self.assertFalse(any(m.get("method") == "mining.authorize" for role, m in w.messages if role == "FEE"))
    def test_reference_failure_is_fatal_not_reconnected(self):
        w = World(); w.engine.valid = False
        with self.assertRaises(miner.VerificationError): w.run()
        self.assertEqual(len(w.calls), 1); self.assertFalse(w.engine.active)
    def test_full_duplicate_cache_is_fatal(self):
        w = World()
        with patch.object(miner.Session, "drain", side_effect=miner.CacheFull("full")):
            with self.assertRaises(miner.CacheFull): w.run()
        self.assertEqual(len(w.calls), 1); self.assertFalse(w.engine.active)
    def test_fee_rejections_are_not_user_rejections(self):
        w = World(); w.reject_shares = {"FEE"}; r = w.run(102)
        self.assertEqual(r["user_stats"]["rejected"], 0)
        self.assertGreaterEqual(r["fee_stats"]["rejected"], 1)
    def test_repeated_cycles_do_not_overcharge(self):
        w = World(); r = w.run(405)
        self.assertEqual(r["fee_windows"], 4)
        self.assertLessEqual(r["fee_active_seconds"] / (r["fee_active_seconds"] + r["user_active_seconds"]), 0.010001)
    def test_interrupt_stops_owned_engine_and_closes_connection(self):
        w = World()
        with patch.object(miner.Session, "drain", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt): w.run()
        self.assertFalse(w.engine.active); self.assertTrue(all(c.closed for c in w.connections))


class ImmediateStandby:
    """Prepare in the caller for deterministic fake-clock scheduling."""
    def __init__(self, connector, config, clock, deadline):
        state = object.__new__(fee.StandbyConnection)
        state.lock, state.cancelled, state.prepared = threading.Lock(), False, None
        state.prepare(connector, config, clock, deadline)
        self.state = state

    def take(self):
        return self.state.take()

    def close(self):
        self.state.close()


class StandbyTests(unittest.TestCase):
    def run_warm(self, world, duration=135, standby_factory=ImmediateStandby):
        display = fee.FeeDisplay(world.engine, world.logs.append, 10, world.clock)
        return fee.run_pool(world.engine, USER, duration, display, policy=fee.Policy(99, 1),
                            clock=world.clock, sleep=world.clock.advance,
                            connectors={r: world.connector(r) for r in ("USER", "FEE")},
                            timer_factory=FakeTimer, standby_factory=standby_factory)

    def test_both_directions_prepare_and_route_verified_shares(self):
        w = World()
        r = self.run_warm(w)
        self.assertEqual([c[0] for c in w.calls], ["USER", "FEE", "USER"])
        self.assertLess(w.calls[1][1], 99)
        self.assertEqual(r["fee_windows"], 1)
        self.assertGreater(r["fee_active_seconds"], 0)
        self.assertLessEqual(r["fee_active_seconds"], 1.000001)
        self.assertGreaterEqual(r["user_stats"]["accepted"], 2)
        self.assertGreaterEqual(r["fee_stats"]["accepted"], 1)
        for role, m in w.messages:
            if m.get("method") == "mining.submit":
                self.assertEqual(m["params"][0], USER["worker"] if role == "USER"
                                 else fee.fee_config(USER)["worker"])
        for role in ("user_stats", "fee_stats"):
            self.assertEqual(r[role]["rejected"] + r[role]["unresolved"], 0)
        self.assertEqual(len([l for l in w.logs if "Standby job activated" in l]), 2)
        epochs = [x[1] for x in w.engine.jobs]
        self.assertEqual(epochs, sorted(set(epochs)))
        self.assertTrue(all(c.closed for c in w.connections))

    def test_fee_failure_skips_without_reconnecting_user(self):
        w = World()
        w.bad_fee_auth = True
        r = self.run_warm(w)
        self.assertEqual([c[0] for c in w.calls], ["USER", "FEE"])
        self.assertEqual(r["skipped_fee_windows"], 1)
        self.assertEqual(r["fee_active_seconds"], 0)
        self.assertFalse(any(c.submissions for c in w.connections if c.role == "FEE"))
        self.assertTrue(all(c.closed for c in w.connections))

    def test_invalidated_fee_standby_leaves_user_mining(self):
        class InvalidFeeStandby(ImmediateStandby):
            def take(self):
                prepared = super().take()
                if prepared:
                    prepared[0].frames.append({"method": "mining.set_difficulty", "params": [2]})
                return prepared
        w = World()
        r = self.run_warm(w, standby_factory=InvalidFeeStandby)
        self.assertEqual([c[0] for c in w.calls], ["USER", "FEE"])
        self.assertEqual(r["skipped_fee_windows"], 1)
        self.assertEqual(r["fee_active_seconds"], 0)
        self.assertEqual(len(w.engine.jobs), 1)
        self.assertTrue(all(c.closed for c in w.connections))

    def test_invalidated_user_standby_falls_back_without_extending_fee(self):
        class InvalidUserStandby(ImmediateStandby):
            def take(self):
                prepared = super().take()
                if prepared and prepared[0].role == "USER":
                    prepared[0].frames.append({"method": "mining.set_difficulty", "params": [2]})
                return prepared
        w = World()
        r = self.run_warm(w, standby_factory=InvalidUserStandby)
        self.assertEqual([c[0] for c in w.calls], ["USER", "FEE", "USER", "USER"])
        self.assertEqual(len(w.connections[2].submissions), 0)
        self.assertGreaterEqual(r["user_stats"]["accepted"], 2)
        self.assertGreaterEqual(r["fee_stats"]["accepted"], 1)
        self.assertLessEqual(r["fee_active_seconds"], 1.000001)
        self.assertTrue(all(r[role]["unresolved"] == r[role]["rejected"] == 0
                            for role in ("user_stats", "fee_stats")))
        epochs = [x[1] for x in w.engine.jobs]
        self.assertEqual(epochs, sorted(set(epochs)))
        self.assertTrue(all(c.closed for c in w.connections))

    def test_end_before_fee_is_due_does_not_open_fee_socket(self):
        w = World()
        r = self.run_warm(w, 98)
        self.assertEqual(r["fee_windows"], 0)
        self.assertEqual([c[0] for c in w.calls], ["USER"])
        self.assertTrue(all(c.closed for c in w.connections))

    def test_prepare_leaves_engine_alone_and_refresh_rejects_invalidated_job(self):
        w = World()
        w.engine.active = True
        ready = ImmediateStandby(w.connector("FEE"), fee.fee_config(USER), w.clock, 1).take()
        self.assertIsNotNone(ready)
        conn, _, session = ready
        self.addCleanup(conn.close)
        self.assertIsNone(session.engine)
        self.assertFalse(session.running)
        self.assertTrue(w.engine.active)
        self.assertFalse(w.engine.jobs or conn.submissions)
        conn.frames.append({"method": "mining.set_difficulty", "params": [2]})
        self.assertFalse(fee.refresh_standby(ready))
        self.assertTrue(w.engine.active)

    def test_real_socket_handoff_with_watchdog(self):
        engine = Engine()
        messages, servers, logs = [], [], []
        errors = []

        def connector(role):
            def connect(config, timeout):
                client, server = socket.socketpair()
                client.settimeout(timeout)
                def serve():
                    try:
                        with server, server.makefile("rb") as stream:
                            for raw in stream:
                                msg = json.loads(raw)
                                method, ident = msg["method"], msg["id"]
                                messages.append((role, method, msg["params"]))
                                if method == "mining.subscribe":
                                    pub = "34" if role == "USER" else "45"
                                    frames = [{"id": ident, "result": ["local", "a1", 1, pub * 32]}]
                                elif method == "mining.authorize":
                                    frames = [{"id": ident, "result": True},
                                              {"method": "mining.set_difficulty", "params": [1]},
                                              {"method": "mining.notify", "params":
                                               ["local-" + role, "1234", "56" * 32, "xel/v3", True]}]
                                elif method == "mining.submit":
                                    frames = [{"id": ident, "result": True}]
                                else:
                                    raise AssertionError(method)
                                server.sendall(b"".join(json.dumps(frame).encode() + b"\n" for frame in frames))
                    except Exception as error:
                        errors.append(error)
                thread = threading.Thread(target=serve, daemon=True)
                servers.append(thread)
                thread.start()
                return client
            return connect

        # Use the production threaded standby, timer, and real stream sockets.
        # The short policy exists only inside this fake-pool test.
        display = fee.FeeDisplay(engine, logs.append, 100)
        result = fee.run_pool(engine, USER, 11.0, display, policy=fee.Policy(9.9, 0.1),
                              connectors={role: connector(role) for role in ("USER", "FEE")})
        for thread in servers:
            thread.join(1)
            self.assertFalse(thread.is_alive())
        self.assertFalse(errors)
        self.assertEqual(result["fee_windows"], 1)
        self.assertGreater(result["fee_active_seconds"], 0)
        self.assertLess(result["fee_active_seconds"], 0.15)
        self.assertEqual(len([line for line in logs if "Standby job activated" in line]), 2)
        self.assertEqual([(role, params[0]) for role, method, params in messages if method == "mining.authorize"],
                         [("USER", USER["wallet"]), ("FEE", fee.FEE_WALLET), ("USER", USER["wallet"])])
        self.assertEqual([(role, params[1]) for role, method, params in messages if method == "mining.submit"],
                         [("USER", "local-USER"), ("FEE", "local-FEE"), ("USER", "local-USER")])
        self.assertEqual(result["user_stats"]["accepted"], 2)
        self.assertEqual(result["fee_stats"]["accepted"], 1)
        self.assertTrue(all(result[role]["unresolved"] == result[role]["rejected"] == 0
                            for role in ("user_stats", "fee_stats")))
        self.assertFalse(engine.active)

    def test_cancelled_connector_closes_late_socket_without_authorizing(self):
        entered, release, closed = threading.Event(), threading.Event(), threading.Event()
        class LateSocket:
            def close(self):
                closed.set()
        def connect(config, timeout):
            entered.set()
            release.wait(1)
            return LateSocket()
        standby = fee.StandbyConnection(connect, USER, time.monotonic, time.monotonic() + 1)
        try:
            self.assertTrue(entered.wait(1))
            self.assertIsNone(standby.take())
        finally:
            release.set()
        self.assertTrue(closed.wait(1))
        self.assertIsNone(standby.take())


class ConnectorTests(unittest.TestCase):
    def test_failed_connection_is_bounded(self):
        connector = fee.BoundedConnector()
        with patch.object(socket, "create_connection", side_effect=OSError("refused")):
            with self.assertRaises(OSError): connector(USER, 0.2)
    def test_late_connection_is_closed(self):
        release = threading.Event()
        class Sock:
            closed = False
            def settimeout(self, x): pass
            def close(self): self.closed = True
        sock = Sock()
        def blocked(*a, **kw): release.wait(1); return sock
        connector = fee.BoundedConnector()
        with patch.object(socket, "create_connection", blocked):
            try:
                with self.assertRaises(TimeoutError): connector(USER, 0.01)
                with self.assertRaises(OSError): connector(USER, 0.01)
            finally:
                release.set(); connector.pending.join(1)
        self.assertTrue(sock.closed)
    def test_tls_certificate_validation_is_used(self):
        class Sock:
            def settimeout(self, x): pass
            def close(self): pass
        s = Sock()
        with patch.object(socket, "create_connection", return_value=s), patch.object(fee.ssl, "create_default_context") as ctx:
            ctx.return_value.wrap_socket.return_value = s
            c = fee.BoundedConnector()({**USER, "pool": "stratum+ssl://pool.invalid:443"}, 0.5)
            ctx.assert_called_once_with()
            ctx.return_value.wrap_socket.assert_called_once_with(s, server_hostname="pool.invalid")
            c.close()



class IdleRecoveryTests(unittest.TestCase):
    def run_world(self, duration):
        w = World()
        display = fee.FeeDisplay(w.engine, w.logs.append, 10, w.clock)
        result = fee.run_pool(w.engine, USER, duration, display, policy=fee.Policy(990, 10),
                             clock=w.clock, sleep=w.clock.advance,
                             connectors={r: w.connector(r) for r in ("USER", "FEE")},
                             timer_factory=FakeTimer, standby_factory=None)
        return w, result

    def test_stale_open_connection_reconnects_after_idle_bound(self):
        w, r = self.run_world(170)
        self.assertEqual([c[0] for c in w.calls], ["USER", "USER"])
        self.assertEqual(r["user_stats"]["reconnects"], 1)
        self.assertGreaterEqual(r["user_stats"]["accepted"], 2)
        self.assertLess(r["user_active_seconds"], 145)
        self.assertEqual(r["fee_windows"], 0)
        self.assertTrue(all(c.closed for c in w.connections))
        self.assertFalse(w.engine.active)

    def test_valid_active_work_is_not_reconnected_for_no_share(self):
        w, r = self.run_world(110)
        self.assertEqual([c[0] for c in w.calls], ["USER"])
        self.assertEqual(r["user_stats"]["reconnects"], 0)
        self.assertEqual(r["fee_windows"], 0)



class FinalReplyBoundaryTests(unittest.TestCase):
    def run_boundary(self, release=1.0, accepted=True, fragment=False):
        world = World()
        class BoundaryConnection(Connection):
            def __init__(self, *args):
                super().__init__(*args); self.held = None; self.part = None
            def sendall(self, data):
                message = json.loads(data)
                if message.get("method") == "mining.submit":
                    self.submissions.append(message)
                    self.world.messages.append((self.role, message))
                    self.held = json.dumps({"id":message["id"], "result":accepted}).encode()+b"\n"
                else: super().sendall(data)
            def recv(self, size):
                if self.frames: return super().recv(size)
                self.world.clock.advance(0.05)
                if self.world.clock() >= release and self.held:
                    data, self.held = self.held, None
                    if fragment:
                        self.part = data[7:]; return data[:7]
                    return data
                if self.part:
                    data, self.part = self.part, None; return data
                raise socket.timeout()
        def connector(config, timeout):
            world.calls.append(("USER",world.clock(),dict(config)))
            conn=BoundaryConnection(world,"USER");world.connections.append(conn);return conn
        display=fee.FeeDisplay(world.engine, world.logs.append,10,world.clock)
        result=fee.run_pool(world.engine,USER,1.0,display,clock=world.clock,
                            sleep=world.clock.advance,connectors={"USER":connector,"FEE":connector},timer_factory=FakeTimer, standby_factory=None)
        self.assertFalse(world.engine.active)
        self.assertEqual(len(world.engine.jobs),1)
        self.assertEqual(sum(len(c.submissions) for c in world.connections),1)
        self.assertTrue(all(c.closed for c in world.connections))
        self.assertLessEqual(world.clock(),2.051)
        return result
    def test_reply_received_at_deadline_is_retained(self):
        r=self.run_boundary();self.assertEqual(r["user_stats"]["accepted"],1);self.assertEqual(r["user_stats"]["unresolved"],0)
    def test_delayed_reply_after_hashing_stops_is_retained(self):
        r=self.run_boundary(release=1.3);self.assertEqual(r["user_stats"]["accepted"],1);self.assertEqual(r["user_stats"]["unresolved"],0)
    def test_fragmented_reply_across_deadline_is_retained(self):
        r=self.run_boundary(fragment=True);self.assertEqual(r["user_stats"]["accepted"],1);self.assertEqual(r["user_stats"]["unresolved"],0)
    def test_missing_reply_stays_unresolved(self):
        r=self.run_boundary(release=100);self.assertEqual(r["user_stats"]["accepted"],0);self.assertEqual(r["user_stats"]["unresolved"],1)
    def test_rejection_is_not_changed_to_acceptance(self):
        r=self.run_boundary(accepted=False);self.assertEqual(r["user_stats"]["accepted"],0);self.assertEqual(r["user_stats"]["rejected"],1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
