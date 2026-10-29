#!/usr/bin/env python3
"""Rig-local correctness gates. Saved Rust answers are replayed, not rerun here."""
from pathlib import Path
import argparse
import collections
import ctypes as C
import json
import os
import sys
import time
ROOT = Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'tools'))
from public_common import need, sha, utc, verify_package, atomic_json, platform_check, conflict_check, take_lock
import miner
import topology
import kernel_lab

def kernel_check():
    platform_check()
    lock_fd = take_lock()  # Process-lifetime lock.
    conflict_check()
    verify_package(ROOT)
    build=json.loads((ROOT/'build/build.json').read_text())
    need(build.get('status')=='built_pending_qualification' and build.get('source_manifest_sha256')==sha(ROOT/'SOURCE-MANIFEST.json'), 'Build source identity mismatch')
    libpath=ROOT/'build/liboverxelis.so'
    need(sha(libpath)==build['library_sha256'],'Unrecognized compiled library')
    need(miner.load_native(libpath).nx_selftest()==0,'Official-vector native self-test failed')
    inputs=(ROOT/'reference/rig-golden-inputs.txt').read_text().splitlines()
    expected=(ROOT/'reference/rig-rust-hashes.txt').read_text().splitlines()
    need(len(inputs)==len(expected)==1031,'Incomplete retained Rust corpus')
    lib=kernel_lab.bindings(libpath)
    names=['xelis_hash_v3','xelis_hash_v3_opt','xelis_hash_v3_experimental','xelis_hash_v3_exp_sqrt']
    pads=[(C.c_uint64*kernel_lab.WORDS)() for _ in names]
    outs=[(kernel_lab.U8*32)() for _ in names]
    for i,(inp,gold) in enumerate(zip(inputs,expected)):
        data=bytes.fromhex(inp); need(len(data)==112 and len(bytes.fromhex(gold))==32,'Invalid retained vector')
        for name,pad,out in zip(names,pads,outs):
            blob=(kernel_lab.U8*112).from_buffer_copy(data)
            getattr(lib,name)(blob,out,pad)
        need(all(bytes(o).hex()==gold for o in outs),'Hash differs from saved Rust output at input '+str(i))
        need(all(bytes(p)==bytes(pads[0]) for p in pads[1:]),'Full scratchpad mismatch at '+str(i))
    report={'utc':utc(),'passed':True,'library_sha256':sha(libpath),'cases':1031,'c_implementations':4,
            'full_scratchpad_comparisons':1031,'retained_rust_output_replay':True,'rust_executed_on_rig':False,
            'inputs_sha256':sha(ROOT/'reference/rig-golden-inputs.txt'),'expected_sha256':sha(ROOT/'reference/rig-rust-hashes.txt')}
    atomic_json(ROOT/'evidence/kernel-qualification.json',report)
    print('PASS: 1,031 inputs, four C implementations, full scratchpad comparisons, saved Rust hash answers.',flush=True)

if __name__ == '__main__':
    try: kernel_check()
    except Exception as error:
        print('QUALIFICATION FAILED: '+type(error).__name__+': '+str(error),file=sys.stderr)
        raise SystemExit(1)
