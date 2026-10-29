#!/usr/bin/env python3
"""JayXelis Next: original standard-library XELIS v3 Stratum control plane.

Protocol: https://docs.xelis.io/developers-api/stratum
No fee, wallet default, scheduler, shell invocation or automatic installation.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import math
import os
from pathlib import Path
import secrets
import socket
import ssl
import time
from collections import OrderedDict
from dataclasses import asdict, dataclass
from urllib.parse import urlsplit

import topology

VERSION = "JayXelisNext/0.3.0-research"
MAX_FRAME = 65536
MAX_TARGET = (1 << 256) - 1
KERNELS = {"reference": 0, "rc1": 1, "experimental": 2, "experimental-sqrt": 3}
PAGES = {"ordinary": 0, "hugetlb": 1}


class ProtocolError(ValueError):
    pass


class AuthorizationError(ProtocolError):
    pass


class CacheFull(ProtocolError):
    pass


class VerificationError(RuntimeError):
    """Fatal local correctness failure; transport reconnection cannot fix it."""
    pass


def fixed_hex(value, size: int) -> bytes:
    if not isinstance(value, str) or len(value) != size * 2 or any(c not in "0123456789abcdefABCDEF" for c in value):
        raise ProtocolError("invalid hexadecimal field")
    return bytes.fromhex(value)


def extranonce(value, size) -> bytes:
    if isinstance(size, bool) or not isinstance(size, int) or not 0 <= size <= 32:
        raise ProtocolError("invalid extranonce length")
    # Pools may send a prefix shorter than the announced field. Right-zero-pad
    # to the complete 32-byte consensus field; never append uncontrolled bytes.
    if not isinstance(value, str) or len(value) % 2 or len(value) > size * 2:
        raise ProtocolError("invalid extranonce")
    return fixed_hex(value, len(value) // 2).ljust(32, b"\0")


def difficulty_target(value) -> tuple[int, bytes]:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_TARGET:
        raise ProtocolError("difficulty must be a positive integer")
    return value, (MAX_TARGET // value).to_bytes(32, "big")


def parse_endpoint(value: str) -> tuple[str, int, bool]:
    if not isinstance(value, str):
        raise ValueError("pool must be a stratum URL")
    parsed = urlsplit(value)
    if parsed.scheme not in ("stratum+tcp", "stratum+ssl", "stratum+tls"):
        raise ValueError("pool scheme must be stratum+tcp or stratum+ssl")
    try:
        port = parsed.port
    except ValueError:
        raise ValueError("invalid pool port") from None
    if not parsed.hostname or port is None or not 1 <= port <= 65535 or parsed.username or parsed.password or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError("pool must contain only a host and explicit port")
    return parsed.hostname, port, parsed.scheme != "stratum+tcp"


def validate_config(config: dict) -> dict:
    if not isinstance(config, dict):
        raise ValueError("config must be an object")
    parse_endpoint(config.get("pool"))
    for key in ("wallet", "worker"):
        value = config.get(key)
        if not isinstance(value, str) or not 1 <= len(value) <= 512 or any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError(f"config requires a valid {key}")
    password = config.get("password", "x")
    if not isinstance(password, str) or len(password) > 512 or any(ord(c) < 32 or ord(c) == 127 for c in password):
        raise ValueError("invalid password")
    checked = dict(config)
    checked["password"] = password
    return checked


def guard_cpu_miners(proc: Path = Path("/proc")) -> None:
    """Best-effort detection of known CPU miners, not a system-wide lock.

    Fail closed on matches or inspection denial; never expose process args.
    Other software can begin running after this snapshot.
    """
    for entry in proc.iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            comm = (entry / "comm").read_text().strip().lower()
            args = (entry / "cmdline").read_bytes().split(b"\0")
        except (FileNotFoundError, ProcessLookupError):
            continue  # The process exited during inspection.
        except PermissionError:
            raise RuntimeError("cannot inspect running processes for CPU exclusivity") from None
        tokens = [arg.decode("utf-8", "replace") for arg in args if arg]
        # SRB may enable CPU mining through a configuration file or its general
        # algorithm flag. Only an explicit disable-cpu exempts this known miner.
        active_srb = comm == "srbminer-multi" and "--disable-cpu" not in tokens
        known_python = comm.startswith("python") and any(Path(t).name in ("jayxelis.py", "miner.py") for t in tokens[1:])
        if comm.startswith("xmrig") or active_srb or known_python:
            raise RuntimeError("another CPU miner is running")


class NativeEngine:
    def __init__(self, cpus: list[int], kernel: int, page_mode: int, library: Path | None = None):
        self.lib = load_native(library)
        self.handle = self.lib.nx_create(len(cpus), (ctypes.c_int * len(cpus))(*cpus), kernel, page_mode)
        if not self.handle:
            raise RuntimeError("native worker creation failed")

    def set_job(self, blob: bytes, target: bytes, epoch: int, nonce_start: int):
        if len(blob) != 112 or len(target) != 32:
            raise ValueError("invalid native job")
        code = self.lib.nx_set_job(self.handle, ctypes.create_string_buffer(blob), ctypes.create_string_buffer(target), epoch, nonce_start)
        if code:
            raise RuntimeError("native job rejected")

    def pause(self):
        self.lib.nx_pause(self.handle)

    def pop(self):
        epoch, nonce, digest = ctypes.c_uint64(), ctypes.c_uint64(), ctypes.create_string_buffer(32)
        code = self.lib.nx_pop(self.handle, ctypes.byref(epoch), ctypes.byref(nonce), digest)
        if code == 0:
            return None
        if code != 1:
            raise RuntimeError("native share queue failed")
        return epoch.value, nonce.value, digest.raw

    def count(self):
        return self.lib.nx_count(self.handle)

    def dropped(self):
        return self.lib.nx_dropped(self.handle)

    def pages(self):
        return self.lib.nx_pages(self.handle)

    def verify(self, work: bytes, digest: bytes) -> bool:
        expected = ctypes.create_string_buffer(32)
        return (self.lib.nx_hash(ctypes.create_string_buffer(work), expected, 0) == 0
                and expected.raw == digest)

    def close(self):
        if self.handle:
            self.lib.nx_destroy(self.handle)
            self.handle = None


def load_native(library: Path | None = None):
    lib = ctypes.CDLL(str(library or Path(__file__).resolve().parent / "build/libjayxelis_next.so"))
    pointer, u64 = ctypes.c_void_p, ctypes.c_uint64
    lib.nx_create.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_int), ctypes.c_int, ctypes.c_int]
    lib.nx_create.restype = pointer
    lib.nx_destroy.argtypes, lib.nx_destroy.restype = [pointer], None
    lib.nx_set_job.argtypes = [pointer, pointer, pointer, u64, u64]
    lib.nx_set_job.restype = ctypes.c_int
    lib.nx_pause.argtypes, lib.nx_pause.restype = [pointer], None
    lib.nx_pop.argtypes = [pointer, ctypes.POINTER(u64), ctypes.POINTER(u64), pointer]
    lib.nx_pop.restype = ctypes.c_int
    for name in ("nx_count", "nx_dropped"):
        getattr(lib, name).argtypes = [pointer]
        getattr(lib, name).restype = u64
    lib.nx_pages.argtypes, lib.nx_pages.restype = [pointer], ctypes.c_int
    lib.nx_selftest.argtypes, lib.nx_selftest.restype = [], ctypes.c_int
    lib.nx_hash.argtypes, lib.nx_hash.restype = [pointer, pointer, ctypes.c_int], ctypes.c_int
    return lib


@dataclass
class Stats:
    submitted: int = 0
    accepted: int = 0
    rejected: int = 0
    unresolved: int = 0
    accepted_work: int = 0
    rejected_work: int = 0
    unresolved_work: int = 0
    stale_local: int = 0
    duplicates_local: int = 0
    invalid_local: int = 0
    reconnects: int = 0


@dataclass
class Job:
    label: str
    blob: bytes
    epoch: int
    difficulty: int
    target: bytes
    created: float


@dataclass
class Pending:
    kind: str
    sent: float
    difficulty: int = 0
    epoch: int = 0


class Session:
    """Single-threaded protocol state; engine workers never access socket state."""
    def __init__(self, engine, config: dict, send, *, clock=time.monotonic, stats=None,
                 seen=None, nonce_start=None, max_seen=32768, max_pending=256,
                 job_timeout=120.0, share_timeout=30.0, epoch_start=1):
        self.engine, self.config, self.send, self.clock = engine, validate_config(config), send, clock
        self.stats = stats if stats is not None else Stats()
        self.seen = seen if seen is not None else set()
        self.max_seen, self.max_pending = max_seen, max_pending
        self.job_timeout, self.share_timeout = job_timeout, share_timeout
        self.nonce_start = secrets.randbits(63) if nonce_start is None else nonce_start
        self.next_id, self.next_epoch = 1, epoch_start
        self.pending: dict[int, Pending] = {}
        self.jobs: OrderedDict[int, Job] = OrderedDict()
        self.active: Job | None = None
        self.extra = self.public = None
        self.difficulty = self.target = None
        self.subscribed = self.authorized = self.running = False
        self.wait_notify = False
        self.deferred_notify = None

    def request(self, method: str, params: list, kind: str, difficulty=0, epoch=0):
        ident = self.next_id
        self.next_id += 1
        self.pending[ident] = Pending(kind, self.clock(), difficulty, epoch)
        self.send({"id": ident, "method": method, "params": params})
        return ident

    def start(self):
        self.pause()
        self.request("mining.subscribe", [VERSION, ["xel/v3"]], "subscribe")
        self.request("mining.authorize", [self.config["wallet"], self.config["worker"], self.config["password"]], "authorize")

    def pause(self):
        self.engine.pause()
        self.running = False

    def activate(self):
        if (self.subscribed and self.authorized and self.active and not self.wait_notify
                and self.clock() - self.active.created < self.job_timeout
                and sum(p.kind == "submit" for p in self.pending.values()) < self.max_pending):
            if not self.running:
                self.engine.set_job(self.active.blob, self.active.target, self.active.epoch, self.nonce_start)
                self.running = True

    def handle(self, message: dict):
        try:
            self._handle(message)
        except (ProtocolError, TypeError, KeyError, OverflowError):
            self.pause()
            raise

    def _handle(self, message: dict):
        if not isinstance(message, dict):
            raise ProtocolError("JSON frame must be an object")
        method = message.get("method")
        if method is None:
            ident = message.get("id")
            if isinstance(ident, bool) or not isinstance(ident, int) or ident not in self.pending:
                return  # Late responses cannot resolve a different request.
            pending = self.pending.pop(ident)
            ok = message.get("error") is None
            if pending.kind == "subscribe":
                result = message.get("result")
                if not ok or not isinstance(result, list) or len(result) != 4 or not isinstance(result[0], str):
                    raise ProtocolError("subscription failed")
                self.extra = extranonce(result[1], result[2])
                self.public = fixed_hex(result[3], 32)
                self.subscribed = True
            elif pending.kind == "authorize":
                if not ok or message.get("result") is not True:
                    self.authorized = False
                    raise AuthorizationError("worker authorization failed")
                self.authorized = True
            elif pending.kind == "submit":
                if ok and message.get("result") is True:
                    self.stats.accepted += 1
                    self.stats.accepted_work += pending.difficulty
                else:
                    self.stats.rejected += 1
                    self.stats.rejected_work += pending.difficulty
                    error = message.get("error")
                    code = error.get("code") if isinstance(error, dict) else error[0] if isinstance(error, list) and error else None
                    if code == 24:
                        self.authorized = False
                        self.pause()
                        raise AuthorizationError("pool revoked authorization")
                    if code == 21:
                        self.jobs.pop(pending.epoch, None)
                        if self.active and self.active.epoch == pending.epoch:
                            self.pause()
                            self.wait_notify = True
            self.consume_deferred()
            self.activate()
            return
        params = message.get("params", [])
        if not isinstance(params, list):
            raise ProtocolError("invalid notification parameters")
        if method == "mining.set_difficulty":
            if len(params) != 1:
                raise ProtocolError("invalid difficulty notification")
            self.difficulty, self.target = difficulty_target(params[0])
            self.wait_notify = True
            self.pause()
            self.consume_deferred()
        elif method == "mining.set_extranonce":
            if len(params) not in (2, 3):
                raise ProtocolError("invalid extranonce notification")
            self.extra = extranonce(params[0], params[1])
            if len(params) == 3:
                self.public = fixed_hex(params[2], 32)
            self.wait_notify = True
            self.jobs.clear()
            self.active = None
            self.deferred_notify = None
            self.pause()
        elif method == "mining.notify":
            self.new_job(params)
        elif method == "mining.ping":
            self.send({"id": message.get("id"), "method": "mining.pong", "params": []})
        # Unknown optional methods and mining.print are ignored; pool messages
        # may contain credentials or terminal escapes and are never logged.

    def new_job(self, params: list):
        if len(params) != 5 or not isinstance(params[0], str) or not 1 <= len(params[0]) <= 256 or not isinstance(params[4], bool):
            raise ProtocolError("invalid mining job")
        if any(ord(c) < 32 for c in params[0]) or params[3] not in ("xel/v3", "xel/2"):
            raise ProtocolError("unsupported job algorithm or label")
        timestamp = params[1]
        if not isinstance(timestamp, str) or not 1 <= len(timestamp) <= 16 or any(c not in "0123456789abcdefABCDEF" for c in timestamp):
            raise ProtocolError("invalid job timestamp")
        header = fixed_hex(params[2], 32)
        stamp_bytes = int(timestamp, 16).to_bytes(8, "big")
        # Servers may pipeline a valid job ahead of handshake replies. Keep
        # only the latest validated notification; never hash until all gates.
        self.deferred_notify = (params[0], stamp_bytes, header, params[4], self.clock())
        self.consume_deferred()

    def consume_deferred(self):
        if not (self.deferred_notify and self.subscribed and self.authorized
                and self.extra is not None and self.public is not None and self.target is not None):
            return
        label, timestamp, header, clean, created = self.deferred_notify
        self.deferred_notify = None
        blob = header + timestamp + bytes(8) + self.extra + self.public
        self.pause()
        if clean:
            self.jobs.clear()
        # Every notification has an independent lifecycle, even if its work
        # bytes match a previous label. A late rejection of that prior label
        # must not invalidate the current notification. Native nonce streams
        # remain monotonic; exact-input suppression independently stops replay.
        epoch = self.next_epoch
        self.next_epoch += 1
        job = Job(label, blob, epoch, self.difficulty, self.target, created)
        self.jobs[epoch] = job
        self.jobs.move_to_end(epoch)
        while len(self.jobs) > 8:
            self.jobs.popitem(last=False)
        self.active, self.wait_notify = job, False
        self.activate()

    def drain(self):
        self.expire()
        if not self.authorized or not self.subscribed or self.wait_notify or not self.running:
            return
        for _ in range(256):
            if sum(p.kind == "submit" for p in self.pending.values()) >= self.max_pending:
                self.pause()
                break
            found = self.engine.pop()
            if found is None:
                break
            epoch, nonce, digest = found
            job = self.jobs.get(epoch)
            if job is None or self.clock() - job.created >= self.job_timeout:
                self.stats.stale_local += 1
                continue
            if not isinstance(digest, bytes) or len(digest) != 32 or digest > job.target or not 0 <= nonce < (1 << 64):
                self.stats.invalid_local += 1
                self.pause()
                raise VerificationError("invalid native share")
            nonce_bytes = nonce.to_bytes(8, "big")
            work = job.blob[:40] + nonce_bytes + job.blob[48:]
            if not self.engine.verify(work, digest):
                self.stats.invalid_local += 1
                self.pause()
                raise VerificationError("share failed reference hash verification")
            if work in self.seen:
                self.stats.duplicates_local += 1
                continue
            if len(self.seen) >= self.max_seen:
                self.pause()
                raise CacheFull("duplicate cache full; restart with a fresh search session")
            self.seen.add(work)
            self.stats.submitted += 1
            self.request("mining.submit", [self.config["worker"], job.label, nonce_bytes.hex()], "submit", job.difficulty, job.epoch)

    def expire(self):
        now = self.clock()
        if self.active and now - self.active.created >= self.job_timeout:
            self.pause()
            self.wait_notify = True
        for ident, pending in list(self.pending.items()):
            if now - pending.sent < self.share_timeout:
                continue
            del self.pending[ident]
            if pending.kind == "submit":
                self.stats.unresolved += 1
                self.stats.unresolved_work += pending.difficulty
            else:
                self.pause()
                raise ProtocolError("handshake timeout")
        self.activate()

    def disconnect(self):
        self.pause()
        self.authorized = self.subscribed = False
        for pending in self.pending.values():
            if pending.kind == "submit":
                self.stats.unresolved += 1
                self.stats.unresolved_work += pending.difficulty
        self.pending.clear()
        self.jobs.clear()
        self.active = None
        self.deferred_notify = None


class Frames:
    def __init__(self, limit=MAX_FRAME):
        self.buffer = bytearray()
        self.limit = limit

    def feed(self, data: bytes) -> list[dict]:
        self.buffer.extend(data)
        messages = []
        while b"\n" in self.buffer:
            end = self.buffer.index(b"\n")
            if end > self.limit:
                raise ProtocolError("pool frame too large")
            raw = bytes(self.buffer[:end])
            del self.buffer[:end + 1]
            try:
                message = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            except (ValueError, UnicodeError, RecursionError):
                raise ProtocolError("invalid pool JSON") from None
            if not isinstance(message, dict):
                raise ProtocolError("pool frame is not an object")
            messages.append(message)
        if len(self.buffer) > self.limit:
            raise ProtocolError("unterminated pool frame too large")
        return messages


def run_pool(engine, config: dict, duration: float) -> dict:
    host, port, tls = parse_endpoint(config["pool"])
    started, stats, seen = time.monotonic(), Stats(), set()
    deadline, backoff = started + duration, 1.0
    nonce_start = secrets.randbits(63)
    next_epoch = 1
    while time.monotonic() < deadline:
        session = connection = None
        try:
            connection = socket.create_connection((host, port), timeout=min(10, max(0.01, deadline - time.monotonic())))
            if tls:
                # Certificate chain and hostname validation are mandatory.
                connection = ssl.create_default_context().wrap_socket(connection, server_hostname=host)
            connection.settimeout(min(0.1, max(0.01, deadline - time.monotonic())))
            def send(message):
                encoded = json.dumps(message, separators=(",", ":"), allow_nan=False).encode() + b"\n"
                if len(encoded) > MAX_FRAME:
                    raise ProtocolError("outgoing frame too large")
                connection.sendall(encoded)
            session = Session(engine, config, send, stats=stats, seen=seen, nonce_start=nonce_start, epoch_start=next_epoch)
            session.start()
            frames = Frames()
            while time.monotonic() < deadline:
                try:
                    data = connection.recv(8192)
                except socket.timeout:
                    data = None
                if data == b"":
                    raise ConnectionError("pool disconnected")
                if data:
                    for message in frames.feed(data):
                        session.handle(message)
                session.drain()
                if session.authorized:
                    backoff = 1.0
        except (AuthorizationError, CacheFull):
            raise
        except (OSError, ProtocolError, ConnectionError):
            stats.reconnects += 1
        finally:
            if session:
                next_epoch = session.next_epoch
                session.disconnect()
            else:
                engine.pause()
            if connection:
                connection.close()
        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(min(backoff, remaining))
            backoff = min(30.0, backoff * 2)
    elapsed = time.monotonic() - started
    hash_count = engine.count()
    return {"mode": "pool", "seconds": elapsed, "hashes": hash_count, "local_hps": hash_count / elapsed,
            "accepted_work_hps": stats.accepted_work / elapsed, "queue_dropped": engine.dropped(),
            "pages": engine.pages(), **asdict(stats)}


def benchmark(engine, duration: float) -> dict:
    # Fixed public synthetic input, target zero: no pool and no share traffic.
    blob = bytes(range(112))
    started = time.monotonic()
    engine.set_job(blob, bytes(32), 1, 0)
    try:
        while time.monotonic() - started < duration:
            time.sleep(min(0.1, max(0, duration - (time.monotonic() - started))))
    finally:
        engine.pause()
    elapsed = time.monotonic() - started
    hash_count = engine.count()
    return {"mode": "benchmark", "seconds": elapsed, "hashes": hash_count,
            "hps": hash_count / elapsed, "queue_dropped": engine.dropped(), "pages": engine.pages(),
            "power_measured": False}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--benchmark", action="store_true")
    modes.add_argument("--check", action="store_true", help="validate topology/config only; no hashing or network")
    modes.add_argument("--self-test", action="store_true", help="run native correctness checks; no pool")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--library", type=Path, help="native library to load; default: build/libjayxelis_next.so")
    parser.add_argument("--duration", type=float, default=30, help="finite run duration in seconds; default 30")
    parser.add_argument("--threads", type=int)
    parser.add_argument("--cpu-list")
    parser.add_argument("--kernel", choices=KERNELS, default="rc1")
    parser.add_argument("--page-mode", choices=PAGES, default="ordinary")
    args = parser.parse_args(argv)
    engine = None
    try:
        if not math.isfinite(args.duration) or not 0 < args.duration <= 86400:
            raise ValueError("duration must be 0 < seconds <= 86400")
        cpus = topology.select(args.threads, args.cpu_list)
        config = None
        if args.config:
            config = validate_config(json.loads(args.config.read_text()))
        if args.check:
            print(json.dumps({"mode": "check", "config_valid": config is not None, "cpus": cpus,
                              "kernel": args.kernel, "page_mode": args.page_mode, "hashing_started": False}))
            return 0
        if args.self_test:
            guard_cpu_miners()
            code = load_native(args.library).nx_selftest()
            print(json.dumps({"mode": "self-test", "passed": code == 0}))
            return 0 if code == 0 else 1
        if not args.benchmark and config is None:
            raise ValueError("mining requires --config; no pool or wallet defaults")
        guard_cpu_miners()
        if load_native(args.library).nx_selftest() != 0:
            raise RuntimeError("native correctness self-test failed")
        engine = NativeEngine(cpus, KERNELS[args.kernel], PAGES[args.page_mode], args.library)
        result = benchmark(engine, args.duration) if args.benchmark else run_pool(engine, config, args.duration)
        result.update({"cpus": cpus, "kernel": args.kernel, "page_mode": args.page_mode})
        print(json.dumps(result))
        return 0
    except KeyboardInterrupt:
        print(json.dumps({"status": "stopped"}))
        return 130
    except (ValueError, OSError, RuntimeError) as error:
        # OSError messages can contain sensitive config paths or pool data.
        print(json.dumps({"status": "failed", "error_type": type(error).__name__}))
        return 1
    finally:
        if engine:
            engine.close()


if __name__ == "__main__":
    raise SystemExit(main())
