#!/usr/bin/env python3
"""Propose target-specific CPU orders; read topology, start no workers or network.

Requires the 7995WX topology described by validated(): 192 allowed logical CPUs,
96 two-way SMT cores, 12 LLC groups of 16 logical CPUs and four NUMA nodes.
Proposals are not benchmark results and do not establish the fastest placement.
"""
from __future__ import annotations

import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path
import sys

COUNTS = (96, 128, 144, 160, 168, 176, 180, 184, 188, 192)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def members(value, expected_size, label):
    result = tuple(value)
    require(len(result) == expected_size and all(type(cpu) is int and cpu >= 0 for cpu in result),
            label + ' has the wrong shape')
    require(tuple(sorted(set(result))) == result, label + ' must be sorted and unique')
    return result


def validated(records, physical_first):
    records = list(records)
    require(len(records) == 192, 'This tuner requires all 192 allowed logical CPUs')
    require(all(type(record.cpu) is int and record.cpu >= 0 for record in records), 'Invalid CPU identifier')
    cpus = {record.cpu: record for record in records}
    require(len(cpus) == 192, 'Repeated CPU record')
    siblings, caches = {}, {}
    for cpu, record in cpus.items():
        require(type(record.numa) is int and record.numa >= 0, 'Missing or invalid NUMA node')
        siblings[cpu] = members(record.siblings, 2, 'SMT siblings')
        caches[cpu] = members(record.last_cache, 16, 'LLC members')
        require(cpu in siblings[cpu] and cpu in caches[cpu], 'CPU missing from its own topology group')
        require(set(siblings[cpu]) <= cpus.keys() and set(caches[cpu]) <= cpus.keys(),
                'Topology refers to CPUs outside the allowed records')
    for cpu, record in cpus.items():
        for sibling in siblings[cpu]:
            require(siblings[sibling] == siblings[cpu] and caches[sibling] == caches[cpu] and
                    cpus[sibling].numa == record.numa, 'Inconsistent sibling topology')
        for member in caches[cpu]:
            require(caches[member] == caches[cpu] and cpus[member].numa == record.numa,
                    'Inconsistent LLC topology')
    require(len(set(siblings.values())) == 96, 'Expected 96 distinct physical cores')
    require(len(set(caches.values())) == 12, 'Expected 12 distinct LLC groups')
    nodes = sorted({record.numa for record in records})
    require(len(nodes) == 4, 'Expected four NUMA nodes')
    for node in nodes:
        node_cpus = [record.cpu for record in records if record.numa == node]
        require(len(node_cpus) == 48 and len({caches[cpu] for cpu in node_cpus}) == 3,
                'Expected 48 logical CPUs and three LLC groups per NUMA node')
    order = list(physical_first(records))
    require(len(order) == 192 and len(set(order)) == 192 and set(order) == set(cpus),
            'physical_first did not return every allowed CPU exactly once')
    base = order[:96]
    require(len({siblings[cpu] for cpu in base}) == 96,
            'The first physical pass must contain one CPU from each core')
    # Keep each LLC's core order exactly as encountered in the original pass.
    groups = {node: {} for node in nodes}
    for cpu in base:
        groups[cpus[cpu].numa].setdefault(caches[cpu], []).append(cpu)
    require(all(len(cores) == 8 for groups_in_node in groups.values() for cores in groups_in_node.values()),
            'Expected eight physical cores per LLC')
    return cpus, siblings, nodes, groups, base


def select_cpus(records, threads, *, rotation=0, physical_first=None):
    """Return ORDERED CPUs, preserving the original 96-core first pass.

    For every extra SMT worker, advance NUMA node first, then LLC within that
    node, then physical core rank within the LLC. Rotation changes only the
    core rank of added SMTs; it never changes the physical pass.
    """
    require(type(threads) is int and 96 <= threads <= 192, 'threads must be an integer from 96 through 192')
    require(type(rotation) is int and 0 <= rotation <= 7, 'rotation must be an integer from 0 through 7')
    if physical_first is None:
        import topology
        physical_first = topology.physical_first
    cpus, siblings, nodes, groups, base = validated(records, physical_first)
    result = list(base)
    for extra in range(threads - 96):
        node = nodes[extra % 4]
        within_node = extra // 4
        node_groups = list(groups[node].values())
        cores = node_groups[within_node % 3]
        core = cores[(within_node // 3 + rotation) % 8]
        result.append(next(cpu for cpu in siblings[core] if cpu != core))
    require(len(result) == threads and len(set(result)) == threads and set(result) <= cpus.keys(),
            'Invalid balanced worker selection')
    return result


def selection_report(records, cpus):
    by_cpu = {record.cpu: record for record in records}
    node_counts = Counter(by_cpu[cpu].numa for cpu in cpus)
    cache_counts = Counter((by_cpu[cpu].numa, tuple(by_cpu[cpu].last_cache)) for cpu in cpus)
    return {'threads': len(cpus), 'ordered_cpus': cpus,
            'node_counts': [{'node': node, 'workers': count} for node, count in sorted(node_counts.items())],
            'llc_counts': [{'node': node, 'members': list(cache), 'workers': count}
                           for (node, cache), count in sorted(cache_counts.items())]}


def load_topology(source_root):
    path = source_root.resolve(strict=True) / 'topology.py'
    spec = importlib.util.spec_from_file_location('balanced_tuning_topology', path)
    require(spec is not None and spec.loader is not None, 'Cannot load existing topology module')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=Path(__file__).resolve().parents[1], help='Existing miner source tree containing topology.py; defaults to this package')
    parser.add_argument('--threads', type=int, nargs='+', default=list(COUNTS))
    parser.add_argument('--rotation', type=int, default=0)
    args = parser.parse_args(argv)
    topology = load_topology(args.source_root)
    records = topology.inspect()
    report = {'method': 'Original physical pass, then NUMA/LLC round-robin added SMT siblings',
              'rotation': args.rotation, 'native_workers_started': False, 'network_used': False,
              'order_requirement': 'Copy threads and ordered_cpus into public config threads and cpus. Ordered arrays preserve worker order; legacy command-line --cpus strings are sorted.',
              'proposal_only': True, 'fastest_profile_established': False,
              'selections': [selection_report(records, select_cpus(records, threads, rotation=args.rotation,
                                                               physical_first=topology.physical_first))
                             for threads in args.threads]}
    print(json.dumps(report, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
