"""Exact-hash/scratchpad comparisons and native stage timings. Lab evidence only."""
import argparse
import ctypes as C
import json
import os
from pathlib import Path
import platform
import random
import time

ROOT=Path(__file__).resolve().parents[1]
U8=C.c_uint8
WORDS=531*128
GOLD=bytes([105,172,103,40,94,253,92,162,42,252,5,196,236,238,91,218,
            22,157,228,233,239,8,250,57,212,166,121,132,148,205,103,163])

def bindings(path):
    lib=C.CDLL(str(path))
    lib.chacha_init.argtypes=[]; lib.chacha_init.restype=None
    lib.chacha_init()
    for name in ('xelis_hash_v3','xelis_hash_v3_opt','xelis_hash_v3_experimental','xelis_hash_v3_exp_sqrt'):
        f=getattr(lib,name);f.argtypes=[C.POINTER(U8),C.POINTER(U8),C.POINTER(C.c_uint64)];f.restype=None
    return lib

def corpus(n):
    rng=random.Random(20261014)
    edge=[bytes(112),bytes([255])*112,bytes(range(112)),bytes([128])*112,
          bytes([1])*112,bytes([85,170])*56]
    for x in edge: yield x
    for i in range(n):
        b=bytearray(rng.randbytes(112))
        if i%11==0:b[40:48]=((1<<64)-1-i).to_bytes(8,'big')
        yield bytes(b)

def validate(lib,n):
    pads=[(C.c_uint64*WORDS)() for _ in range(4)]
    outputs=[(U8*32)() for _ in range(4)]
    functions=[lib.xelis_hash_v3,lib.xelis_hash_v3_opt,lib.xelis_hash_v3_experimental,lib.xelis_hash_v3_exp_sqrt]
    cases=0
    for data in corpus(n):
        blob=(U8*112).from_buffer_copy(data)
        for f,p,h in zip(functions,pads,outputs):f(blob,h,p)
        if any(bytes(h)!=bytes(outputs[0]) for h in outputs[1:]):
            raise RuntimeError(f'hash mismatch at case {cases}')
        if any(bytes(p)!=bytes(pads[0]) for p in pads[1:]):
            raise RuntimeError(f'entire scratchpad mismatch at case {cases}')
        if not cases and bytes(outputs[0])!=GOLD:raise RuntimeError('official zero vector mismatch')
        cases+=1
    return {'full_hash_cases':cases,'entire_scratchpad_cases':cases,
            'kernels_per_case':4,'seed':20261014,'mismatches':0}

def profile(lib,cases):
    f=lib.nx_profile;f.argtypes=[C.POINTER(U8),C.POINTER(U8),C.POINTER(C.c_uint64),C.POINTER(C.c_uint64)]
    scratch=(C.c_uint64*WORDS)(); out=(U8*32)();t=(C.c_uint64*3)()
    rows=[]
    for i,data in enumerate(corpus(cases)):
        f((U8*112).from_buffer_copy(data),out,scratch,t)
        if i>=6:rows.append(list(t))
    totals=[sum(row[i] for row in rows) for i in range(3)]
    total=sum(totals)
    return {'cases':len(rows),'stage_nanoseconds':dict(zip(['initialize','mix','finalize'],totals)),
            'stage_fractions':dict(zip(['initialize','mix','finalize'],[x/total for x in totals])),
            'notes':'Instrumented single-thread lab wall timing; not hardware counters or target-host profile.'}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--library',type=Path,default=ROOT/'build/libjayxelis_next.so')
    p.add_argument('--cases',type=int,default=256)
    p.add_argument('--profile',action='store_true')
    p.add_argument('--output',type=Path,default=ROOT/'evidence/kernel-correctness.json')
    a=p.parse_args()
    if not 1<=a.cases<=100000:p.error('cases outside 1..100000')
    lib=bindings(a.library)
    start=time.monotonic()
    report={'machine':platform.node(),'cpu_affinity':sorted(os.sched_getaffinity(0)),
       'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'wall_power_measured':False,
       'origin':'Execution environment; inspect machine before interpreting results',
       'validation':validate(lib,a.cases)}
    if a.profile:report['profile']=profile(lib,min(a.cases,256))
    report['elapsed_seconds']=time.monotonic()-start
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
