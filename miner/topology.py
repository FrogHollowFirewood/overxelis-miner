"""Read-only Linux CPU topology and explicit, affinity-aware worker selection."""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path


def parse_cpulist(value: str) -> list[int]:
    """Parse Linux cpulists; reject ambiguous repeats, descending ranges and junk."""
    found: set[int] = set()
    if not isinstance(value, str) or not value.strip():
        raise ValueError("CPU list must not be empty")
    for part in value.strip().split(","):
        ends = part.split("-")
        if len(ends) not in (1, 2) or any(not x.isascii() or not x.isdigit() for x in ends):
            raise ValueError("invalid CPU list")
        first, last = int(ends[0]), int(ends[-1])
        if first > last or last > 1048575 or last - first > 65535:
            raise ValueError("invalid CPU range")
        for cpu in range(first, last + 1):
            if cpu in found:
                raise ValueError("CPU list contains duplicates")
            found.add(cpu)
    return sorted(found)


def _read(path: Path, fallback: str = "") -> str:
    try:
        return path.read_text(encoding="ascii").strip()
    except (OSError, UnicodeError):
        return fallback


@dataclass(frozen=True)
class CPU:
    cpu: int
    siblings: tuple[int, ...]
    numa: int | None
    last_cache: tuple[int, ...]


def inspect(sysfs: Path = Path("/sys/devices/system"), allowed=None) -> list[CPU]:
    if allowed is None:
        allowed = sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else list(range(os.cpu_count() or 1))
    allowed = sorted(set(allowed))
    allowed_set = set(allowed)
    records = []
    for number in allowed:
        base = sysfs / "cpu" / f"cpu{number}"
        try:
            siblings = tuple(c for c in parse_cpulist(_read(base / "topology/thread_siblings_list")) if c in allowed_set)
        except ValueError:
            siblings = (number,)
        # Missing topology must never collapse distinct CPUs into a single core.
        if number not in siblings:
            siblings = (number,)
        numa = None
        for path in sorted(base.glob("node[0-9]*")):
            if path.name[4:].isdigit():
                numa = int(path.name[4:])
                break
        highest, last_cache = -1, (number,)
        for path in base.glob("cache/index[0-9]*"):
            level = _read(path / "level")
            kind = _read(path / "type")
            if not level.isdigit() or kind not in ("Unified", "Data") or int(level) < highest:
                continue
            try:
                members = tuple(c for c in parse_cpulist(_read(path / "shared_cpu_list")) if c in allowed_set)
            except ValueError:
                continue
            if number in members:
                highest, last_cache = int(level), members
        records.append(CPU(number, siblings, numa, last_cache))
    return records


def physical_first(records: list[CPU]) -> list[int]:
    """One allowed sibling of every discovered core, then remaining siblings."""
    ordered = sorted(records, key=lambda c: (c.numa if c.numa is not None else -1, c.last_cache, c.cpu))
    used_cores: set[tuple[int, ...]] = set()
    first, remaining = [], []
    for record in ordered:
        if record.siblings in used_cores:
            remaining.append(record.cpu)
        else:
            first.append(record.cpu)
            used_cores.add(record.siblings)
    return first + remaining


def select(threads: int | None = None, cpu_list: str | None = None, records: list[CPU] | None = None) -> list[int]:
    records = inspect() if records is None else records
    allowed = {item.cpu for item in records}
    if not allowed:
        raise ValueError("no allowed CPUs")
    if cpu_list is not None:
        selected = parse_cpulist(cpu_list)
        if set(selected) - allowed:
            raise ValueError("requested CPUs are outside the process affinity")
        if threads is not None and threads != len(selected):
            raise ValueError("--threads must equal the explicit CPU list length")
        return selected
    if threads is None:
        threads = min(96, len({item.siblings for item in records}))
    if isinstance(threads, bool) or not isinstance(threads, int) or not 1 <= threads <= len(allowed):
        raise ValueError("thread count must fit the allowed CPUs")
    return physical_first(records)[:threads]


def report(records: list[CPU] | None = None) -> dict:
    records = inspect() if records is None else records
    return {"allowed_cpus": [c.cpu for c in records], "physical_first": physical_first(records),
            "discovered_cores": len({c.siblings for c in records}),
            "numa_nodes": sorted({c.numa for c in records if c.numa is not None}),
            "cpus": [asdict(c) for c in records]}
