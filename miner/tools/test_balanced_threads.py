"""Synthetic target-topology tests; no inspection or worker creation."""
from dataclasses import replace
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import balanced_threads as tuner

SOURCE = Path(__file__).resolve().parents[1]
topology = tuner.load_topology(SOURCE)


def fixture():
    # Sparse noncontiguous IDs make any hardcoded CPU-number/SMT-offset rule fail.
    records = []
    for node in range(4):
        for llc in range(3):
            cores = []
            for rank in range(8):
                index = node * 24 + llc * 8 + rank
                cores.append((1000 + index * 3, 5000 + index * 5))
            cache = tuple(sorted(cpu for core in cores for cpu in core))
            for core in cores:
                for cpu in core:
                    records.append(topology.CPU(cpu, core, node, cache))
    return list(reversed(records))


EXPECTED = {96:(24,[8,8,8]), 128:(32,[11,11,10]), 144:(36,[12,12,12]),
            160:(40,[14,13,13]), 168:(42,[14,14,14]), 176:(44,[15,15,14]),
            180:(45,[15,15,15]), 184:(46,[16,15,15]), 188:(47,[16,16,15]), 192:(48,[16,16,16])}


class BalancedSelection(unittest.TestCase):
    def setUp(self):
        self.records = fixture()
        self.base = topology.physical_first(self.records)[:96]

    def select(self, threads, records=None, rotation=0, physical_first=None):
        return tuner.select_cpus(self.records if records is None else records, threads, rotation=rotation,
                                 physical_first=physical_first or topology.physical_first)

    def test_all_requested_counts_exact_node_and_llc_balance(self):
        for threads, (per_node, per_cache) in EXPECTED.items():
            with self.subTest(threads=threads):
                cpus = self.select(threads)
                report = tuner.selection_report(self.records, cpus)
                self.assertEqual(len(cpus), threads)
                self.assertEqual(len(set(cpus)), threads)
                self.assertTrue(set(cpus) <= {record.cpu for record in self.records})
                self.assertEqual(cpus[:96], self.base)
                self.assertEqual([row['workers'] for row in report['node_counts']], [per_node] * 4)
                self.assertEqual([row['workers'] for row in report['llc_counts']], per_cache * 4)

    def test_extra_order_cycles_nodes_then_caches(self):
        by_cpu = {record.cpu:record for record in self.records}
        extra = self.select(160)[96:]
        self.assertEqual([by_cpu[cpu].numa for cpu in extra], [0,1,2,3] * 16)
        node0 = [by_cpu[cpu].last_cache for cpu in extra if by_cpu[cpu].numa == 0]
        self.assertEqual(node0[:12], node0[:3] * 4)

    def test_rotation_changes_only_added_siblings_and_can_leave_first_core_single(self):
        for rotation in range(8):
            cpus = self.select(160, rotation=rotation)
            self.assertEqual(cpus[:96], self.base)
            self.assertEqual(len(set(cpus)),160)
        cpus = self.select(160, rotation=1)
        by_cpu = {record.cpu:record for record in self.records}
        first_sibling = next(cpu for cpu in by_cpu[self.base[0]].siblings if cpu != self.base[0])
        self.assertNotIn(first_sibling, cpus)

    def test_all_counts_form_nested_selections_for_fixed_rotation(self):
        for rotation in range(8):
            full = self.select(192, rotation=rotation)
            for threads in EXPECTED:
                self.assertEqual(self.select(threads, rotation=rotation),full[:threads])

    def test_repeated_cpu_rejected(self):
        with self.assertRaisesRegex(ValueError,'Repeated CPU'):
            self.select(160, self.records[:-1] + [self.records[0]])

    def test_missing_record_rejected(self):
        with self.assertRaisesRegex(ValueError,'192 allowed'):
            self.select(160,self.records[:-1])

    def test_inconsistent_siblings_rejected(self):
        records=list(self.records)
        records[0]=replace(records[0], siblings=(records[0].cpu,records[1].cpu))
        with self.assertRaises(ValueError): self.select(160,records)

    def test_repeated_cache_members_rejected(self):
        records=list(self.records)
        group=records[0].last_cache
        records[0]=replace(records[0],last_cache=(group[0],group[0],*group[2:]))
        with self.assertRaisesRegex(ValueError,'sorted and unique'):self.select(160,records)

    def test_inconsistent_numa_rejected(self):
        records=list(self.records);records[0]=replace(records[0],numa=99)
        with self.assertRaises(ValueError):self.select(160,records)

    def test_inconsistent_llc_rejected(self):
        records=list(self.records);records[0]=replace(records[0],last_cache=records[20].last_cache)
        with self.assertRaises(ValueError):self.select(160,records)

    def test_outside_allowed_sibling_rejected(self):
        records=list(self.records);records[0]=replace(records[0],siblings=tuple(sorted((records[0].cpu,999999))))
        with self.assertRaisesRegex(ValueError,'outside the allowed'):self.select(160,records)

    def test_missing_numa_rejected(self):
        records=list(self.records);records[0]=replace(records[0],numa=None)
        with self.assertRaisesRegex(ValueError,'NUMA'):self.select(160,records)

    def test_nonphysical_initial_pass_rejected(self):
        with self.assertRaisesRegex(ValueError,'first physical pass'):
            self.select(160,physical_first=lambda records:sorted(record.cpu for record in records)[::2]+sorted(record.cpu for record in records)[1::2])

    def test_bad_parameters_rejected(self):
        for threads in (95,193,True,160.0,'160'):
            with self.subTest(threads=threads),self.assertRaises(ValueError):self.select(threads)
        for rotation in (-1,8,True,1.0):
            with self.subTest(rotation=rotation),self.assertRaises(ValueError):self.select(160,rotation=rotation)

    def test_order_is_not_a_sorted_cli_cpu_list(self):
        cpus=self.select(160)
        self.assertNotEqual(cpus,sorted(cpus))
        self.assertEqual(set(cpus),set(sorted(cpus)))


if __name__=='__main__':unittest.main(verbosity=2)
