"""Disclosed, user-first fee scheduling for the separate OverXelis beta.2 trial.

The native hash algorithm and original Stratum Session are not modified.
Production policy: 5,940 seconds of active user work, then a fee window whose
60-second wall deadline includes connection setup. No fee catch-up or startup
fee. Restarting this beta resets the schedule. Pool payout is probabilistic;
this is a time allocation, not a guarantee of exactly 1% of coins.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import secrets
import socket
import ssl
import threading
import time

import miner

USER_SECONDS = 5940.0
FEE_SECONDS = 60.0
FEE_WALLET = "xel:pqu4e39zln0g7lx9grdhj3tavuy6e45sjglp9ss9n6lx2zc0w9fqqxhxxvt"
FEE_POOL = "stratum+tcp://xel-us.kryptex.network:7019"


class PhaseEnded(Exception):
    """A scheduled phase ended; this is not a hash or transport failure."""


@dataclass(frozen=True)
class Policy:
    user_seconds: float = USER_SECONDS
    fee_seconds: float = FEE_SECONDS

    def __post_init__(self):
        if (not math.isfinite(self.user_seconds) or not math.isfinite(self.fee_seconds)
                or self.fee_seconds <= 0 or self.user_seconds < 99 * self.fee_seconds):
            raise ValueError("Fee policy must reserve at least 99 user seconds per fee second")


def fee_config(user_config):
    # No user password or payout address is reused in the developer login.
    suffix = hashlib.sha256(user_config["worker"].encode()).hexdigest()[:12]
    return {"pool": FEE_POOL, "wallet": FEE_WALLET,
            "worker": "OverXelis-devfee-" + suffix, "password": "x"}


class MeteredEngine:
    """Single native engine, synchronized phase gate, and active-time accounting.

    User time is bounded conservatively by completed start/pause calls. A fee
    watchdog seals the gate: a late notification cannot reactivate fee hashing.
    Python/OS timers are not a hard real-time guarantee; observed time is logged.
    """
    def __init__(self, native, clock=time.monotonic):
        self.native, self.clock = native, clock
        self.lock = threading.RLock()
        self.role = "USER"
        self.deadline = float("inf")
        self.sealed = False
        self.started = None
        self.totals = {"USER": 0.0, "FEE": 0.0}

    def set_phase(self, role, deadline=float("inf")):
        if role not in self.totals:
            raise ValueError("Unknown role")
        with self.lock:
            if self.started is not None:
                raise RuntimeError("Pause the previous phase before switching")
            self.role, self.deadline, self.sealed = role, deadline, False

    def set_job(self, *args):
        with self.lock:
            if self.sealed or self.clock() >= self.deadline:
                raise PhaseEnded()
            before = self.clock()
            self.native.set_job(*args)
            if self.started is None:
                self.started = before if self.role == "FEE" else self.clock()

    def pause(self):
        with self.lock:
            before = self.clock()
            self.native.pause()
            after = self.clock()
            if self.started is not None:
                # Under-count user work, over-count fee work, rather than charge
                # unobserved paused or startup time as user work.
                end = before if self.role == "USER" else after
                self.totals[self.role] += max(0.0, end - self.started)
                self.started = None

    def seal(self):
        with self.lock:
            self.sealed = True
            self.pause()

    def active_seconds(self, role):
        with self.lock:
            extra = max(0.0, self.clock() - self.started) if self.role == role and self.started is not None else 0.0
            return self.totals[role] + extra

    def __getattr__(self, name):
        return getattr(self.native, name)


class BoundedConnector:
    """Bound DNS/TCP/TLS waiting without running any hashing in the worker.

    At most one outstanding connection thread per role. A late result is closed
    after timeout/cancellation, not adopted by another phase. TLS uses normal
    certificate-chain and hostname verification when requested by the endpoint.
    """
    def __init__(self):
        self.pending = None

    def __call__(self, config, timeout):
        if self.pending is not None and self.pending.is_alive():
            raise OSError("Previous connection attempt is still resolving")
        host, port, tls = miner.parse_endpoint(config["pool"])
        ready, cancelled, guard = threading.Event(), threading.Event(), threading.Lock()
        result = {}

        def connect():
            connection = None
            try:
                connection = socket.create_connection((host, port), timeout=timeout)
                if tls:
                    connection = ssl.create_default_context().wrap_socket(connection, server_hostname=host)
                connection.settimeout(0.1)
                with guard:
                    if not cancelled.is_set():
                        result["connection"] = connection
                        connection = None
            except Exception as error:
                with guard:
                    result["error"] = type(error).__name__
            finally:
                if connection is not None:
                    connection.close()
                ready.set()

        self.pending = threading.Thread(target=connect, name="OverXelis-connect", daemon=True)
        self.pending.start()
        delivered = False
        try:
            if not ready.wait(max(0.001, timeout)):
                raise TimeoutError("Connection deadline expired")
            with guard:
                if "connection" not in result:
                    raise OSError("Pool connection failed")
                connection = result.pop("connection")
                delivered = True
                return connection
        finally:
            if not delivered:
                with guard:
                    cancelled.set()
                    connection = result.pop("connection", None)
                if connection is not None:
                    connection.close()


class FeeDisplay:
    def __init__(self, engine, log, interval, clock=time.monotonic):
        self.engine, self.log, self.interval, self.clock = engine, log, interval, clock
        self.start, self.initial = self.snapshot()
        self.last_time, self.last_count = self.start, self.initial
        self.role = "USER"
        self.stats = {"USER": miner.Stats(), "FEE": miner.Stats()}
        self.gate = None

    def snapshot(self):
        before = self.clock()
        count = self.engine.count()  # One counter read; no double-read inflation.
        after = self.clock()
        return (before + after) / 2, count

    def report(self, running=False, force=False):
        if not force and self.clock() - self.last_time < self.interval:
            return
        now, count = self.snapshot()
        if count < self.last_count:
            raise RuntimeError("Completed-hash counter moved backwards")
        rate = (count - self.last_count) / max(now - self.last_time, 1e-9)
        mean = (count - self.initial) / max(now - self.start, 1e-9)
        self.last_time, self.last_count = now, count
        user, fee = self.stats["USER"], self.stats["FEE"]
        self.log("Local: %.3f kH/s | Session avg: %.3f kH/s | Mode: %s | User accepted: %d | Fee accepted: %d | Rejected: %d | Unresolved: %d | %s" % (
            rate / 1000, mean / 1000, self.role, user.accepted, fee.accepted,
            user.rejected + fee.rejected, user.unresolved + fee.unresolved,
            "hashing" if running else "paused"))
        if self.engine.dropped():
            raise RuntimeError("Share queue overflow; stopping rather than discard work")


def session_class(log, role):
    class LoggedSession(miner.Session):
        def handle(self, message):
            auth, accepted, rejected = self.authorized, self.stats.accepted, self.stats.rejected
            super().handle(message)
            if self.authorized and not auth:
                log("[%s] Pool authorized worker %s." % (role, self.config["worker"]))
            if self.stats.accepted > accepted:
                log("[%s] Share ACCEPTED | Total: %d" % (role, self.stats.accepted))
            if self.stats.rejected > rejected:
                log("[%s] Share REJECTED | Total: %d" % (role, self.stats.rejected))
    return LoggedSession


def settle_pending(session, connection, frames, deadline, clock):
    """Pause hashing; accept only replies to already submitted shares.

    New jobs are ignored during handover. A user's queued submission is never
    re-labelled or forwarded to the developer connection (or vice versa).
    """
    session.pause()
    session.active = None
    session.deferred_notify = None
    session.wait_notify = True
    while clock() < deadline and any(p.kind == "submit" for p in session.pending.values()):
        try:
            connection.settimeout(min(0.1, max(0.001, deadline - clock())))
            data = connection.recv(8192)
            if not data:
                break
            for message in frames.feed(data):
                ident = message.get("id")
                pending = session.pending.get(ident) if type(ident) is int else None
                if message.get("method") is None and pending is not None and pending.kind == "submit":
                    session.handle(message)
        except socket.timeout:
            continue
        except (OSError, miner.ProtocolError):
            break


def run_pool(engine, config, duration, display, *, policy=None, clock=time.monotonic,
             sleep=time.sleep, connectors=None, timer_factory=threading.Timer):
    """Run USER/FEE phases. Injected policy/IO are for deterministic offline tests.

    The desktop CLI does not expose a shortened fee cycle. Native hashing is
    always paused before disconnect/reconnect; epochs are globally increasing.
    """
    policy = Policy() if policy is None else policy
    if not isinstance(policy, Policy):
        raise ValueError("Invalid fee policy")
    if math.isnan(duration) or duration <= 0:
        raise ValueError("Invalid duration")
    configs = {"USER": miner.validate_config(dict(config)), "FEE": miner.validate_config(fee_config(config))}
    connectors = connectors if connectors is not None else {"USER": BoundedConnector(), "FEE": BoundedConnector()}
    started, role, last_fee_user_time = clock(), "USER", 0.0
    overall_deadline = started + duration
    gate = MeteredEngine(engine, clock)
    display.gate = gate
    seen, next_epoch, nonce_start = set(), 1, secrets.randbits(63)
    attempts, skipped = 0, 0
    try:
        while clock() < overall_deadline:
            display.role = role
            fee_deadline = clock() + policy.fee_seconds if role == "FEE" else float("inf")
            phase_deadline = min(overall_deadline, fee_deadline)
            gate.set_phase(role, phase_deadline)
            timer = None
            if role == "FEE":
                attempts += 1
                last_fee_user_time = gate.active_seconds("USER")
                display.log("DEV FEE START | 1% policy | Kryptex | Wallet: " + FEE_WALLET)
                timer = timer_factory(max(0, phase_deadline - clock()), gate.seal)
                timer.daemon = True
                timer.start()
            else:
                display.log("USER MINING | Pool: %s | Worker: %s | Next fee after %.0f active user seconds" % (
                    configs[role]["pool"], configs[role]["worker"], policy.user_seconds))
            backoff, fee_failed = 1.0, False
            try:
                while clock() < phase_deadline:
                    if role == "USER" and gate.active_seconds("USER") - last_fee_user_time >= policy.user_seconds:
                        break
                    session = connection = None
                    frames = miner.Frames()
                    planned_end = False
                    try:
                        gate.pause()
                        connection = connectors[role](configs[role], min(5.0, max(0.001, phase_deadline - clock())))
                        if clock() >= phase_deadline:
                            raise PhaseEnded()
                        connection.settimeout(0.1)
                        def send(message):
                            encoded = json.dumps(message, separators=(",", ":"), allow_nan=False).encode() + b"\n"
                            if len(encoded) > miner.MAX_FRAME:
                                raise miner.ProtocolError("Outgoing frame too large")
                            connection.sendall(encoded)
                        cls = session_class(display.log, role)
                        session = cls(gate, configs[role], send, clock=clock, stats=display.stats[role],
                                      seen=seen, nonce_start=nonce_start, epoch_start=next_epoch)
                        display.log("[%s] Connecting; subscribing and authorizing." % role)
                        session.start()
                        inactive_since = clock()
                        while clock() < phase_deadline:
                            if role == "USER" and gate.active_seconds("USER") - last_fee_user_time >= policy.user_seconds:
                                break
                            if gate.sealed:
                                raise PhaseEnded()
                            try:
                                data = connection.recv(8192)
                            except socket.timeout:
                                data = None
                            if clock() >= phase_deadline:
                                break
                            if data == b"":
                                raise ConnectionError("Pool disconnected")
                            if data:
                                for message in frames.feed(data):
                                    session.handle(message)
                            session.drain()
                            # A TCP connection can stay open after usable jobs stop.
                            # Session.expire() pauses stale work, but does not itself
                            # reconnect. Never leave a rig idle indefinitely.
                            if session.running:
                                inactive_since = None
                            elif inactive_since is None:
                                inactive_since = clock()
                            elif clock() - inactive_since >= 30.0:
                                raise ConnectionError("No usable job for 30 paused seconds")
                            display.report(running=session.running)
                            if engine.dropped():
                                raise RuntimeError("Share queue overflow")
                            if session.authorized:
                                backoff = 1.0
                        planned_end = True
                    except PhaseEnded:
                        planned_end = True
                    except miner.CacheFull:
                        raise  # Never retry with a full unchanged duplicate cache.
                    except miner.AuthorizationError:
                        if role == "USER":
                            raise
                        fee_failed = True
                        display.log("DEV FEE SKIPPED | Authorization failed; no catch-up")
                    except (OSError, miner.ProtocolError):
                        display.stats[role].reconnects += 1
                        if role == "FEE":
                            fee_failed = True
                            display.log("DEV FEE SKIPPED | Connection/protocol failure; no catch-up")
                        else:
                            display.log("USER connection interrupted; hashing paused; retrying.")
                    finally:
                        gate.pause()
                        if session is not None:
                            try:
                                if planned_end and connection is not None:
                                    settle_pending(session, connection, frames,
                                                   min(overall_deadline, clock() + 1.0), clock)
                            finally:
                                next_epoch = max(next_epoch, session.next_epoch)
                                session.disconnect()
                        if connection is not None:
                            connection.close()
                    if planned_end or fee_failed:
                        break
                    remaining = phase_deadline - clock()
                    if remaining > 0:
                        sleep(min(backoff, remaining))
                        backoff = min(30.0, backoff * 2)
            finally:
                gate.seal()
                if timer is not None:
                    timer.cancel()
                    timer.join(timeout=2)
                    if timer.is_alive():
                        raise RuntimeError("Fee watchdog did not finish; stopped for safety")
            if role == "FEE":
                if fee_failed:
                    skipped += 1
                display.log("DEV FEE END | Returning to configured user pool/wallet | Cumulative fee-active seconds: %.3f" % gate.active_seconds("FEE"))
                role = "USER"
            else:
                role = "FEE"
    finally:
        gate.seal()
        display.report(force=True)
        display.log("TIME ACCOUNTING | User-active: %.3f s | Fee-active: %.3f s | Fee windows: %d | Skipped: %d" % (
            gate.active_seconds("USER"), gate.active_seconds("FEE"), attempts, skipped))
    return {"mode": "pool-with-disclosed-dev-fee", "seconds": clock() - started,
            "user_active_seconds": gate.active_seconds("USER"), "fee_active_seconds": gate.active_seconds("FEE"),
            "fee_windows": attempts, "skipped_fee_windows": skipped,
            "user_stats": asdict(display.stats["USER"]), "fee_stats": asdict(display.stats["FEE"]),
            "schedule_resets_on_restart": True, "policy_user_seconds": policy.user_seconds,
            "policy_fee_window_seconds": policy.fee_seconds}
