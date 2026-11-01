# OverXelis Miner 1.0.0-beta.3 · Public source preview 1

Experimental Linux x86-64 CPU miner for XELIS. This is a **source-only prerelease**: build and qualify it on the computer that will mine. No precompiled miner or private user configuration is included.

## Download

Download these two release assets:

- [Latest beta.3 source archive](https://github.com/FrogHollowFirewood/overxelis-miner/releases/download/v1.0.0-beta.3-public-preview.1/OverXelis-Miner-1.0.0-beta.3-public-source-preview.1.tar.gz)
- [Matching SHA-256 checksum](https://github.com/FrogHollowFirewood/overxelis-miner/releases/download/v1.0.0-beta.3-public-preview.1/SHA256SUMS-beta.3-public-source-preview.1.txt)
- [Release page](https://github.com/FrogHollowFirewood/overxelis-miner/releases/tag/v1.0.0-beta.3-public-preview.1)

Archive SHA-256:

```text
a53075dd73977796281780767ff4387c8c788a951630a468b5591fd6731cee12
```

A checksum checks file integrity; it is not a publisher signature.

## What changed

- Optimized two native arithmetic cases, retaining the original fallback and hash behavior.
- Replaced the production native engine's growing duplicate-input cache with bounded lifetime nonce tracking. Reference verification still precedes submission, and tracking persists across jobs, reconnects and USER/FEE transitions.
- Added optional ordered CPU selection with validation before native loading or networking, plus an explicit 7995WX example requesting 192 threads and hugetlb memory. Automatic CPU selection and the generic ordinary-memory configuration remain available.
- Added isolated-process benchmark and actual-worker qualification tools, including a regression fix for interruption during benchmark child launch.

The disclosed developer mining-time allocation remains unchanged: 99 active USER minutes, followed by a fee window of up to 60 seconds. Mining requires `--accept-dev-fee`.

## Recorded validation

On one AMD Threadripper PRO 7995WX desktop, using 192 threads, hugetlb memory and GCC 14.3.0 with a normal non-PGO build:

| Test | Recorded result | Scope |
| --- | --- | --- |
| Matched beta.2 benchmark | 110.234 kH/s | Four separate 60-second samples |
| Matched beta.3 benchmark | 111.168 kH/s | Four separate 60-second samples; **+0.85%** time-weighted throughput |
| Exact public beta.3 pool run | 110.870 kH/s local session average | 300-second run, including startup and job waits; 38 accepted shares, zero rejected |

The benchmark alternated run order and used a fresh process for each sample, with a 15-second warmup. Beta.3's four sample rates ranged from 110.877 to 111.611 kH/s. The public package reproduced the measured candidate's native library byte for byte. These are local completed-hash rates, not a measurement of pool-side hashrate or payouts.

The exact public package passed **124 production tests**, **15 tuning-tool tests**, native self-test, 1,031 saved-Rust-answer cases through four C implementations, and 1,031 entire-scratchpad comparisons. Saved answers were replayed; fresh Rust was not executed. Each of 192 actual hugetlb workers also returned a reference-verified terminal hash with zero queue drops.

The pool run recorded zero rejected, unresolved, locally stale, duplicate or invalid shares, zero reconnects and zero queue drops; normal worker cleanup completed.

[Detailed validation status](https://froghollowfirewood.github.io/overxelis-miner/site-status.html#beta3-validation) · [Sanitized evidence](https://froghollowfirewood.github.io/overxelis-miner/evidence/beta3-validation-20261101.json)

## Build and use

Arrange Python 3.10+, GCC 14 and GNU binutils first. Use the actual absolute GCC14 executable path:

```bash
python3 -I -B build_public.py --compiler /absolute/path/to/gcc14
python3 -I -B qualify_public.py
bash run.sh --self-test
bash run.sh --configure
bash run.sh --check
bash run.sh --accept-dev-fee
```

Stop an existing CPU miner normally before building or mining. The 192-thread hugetlb example requires huge pages and permissions already configured. Enter your own public payout address; the distributed placeholder cannot start mining. Read the included README for requirements, fee policy and memory settings.

## Limits

These finite observations do not establish a universal fastest profile or guaranteed hashrate. No matched 5% advantage over BzMiner is claimed. A full live fee cycle, deliberate live reconnect recovery and a long soak test remain unverified for beta.3. Historical beta.2 results are separate evidence.


---

# Historical release notes

# 1.0.0-beta.2 / public-source-preview.2

Experimental Linux x86-64 CPU source preview. This is an attribution and
packaging correction, not a speed optimization or stable binary release.

## What changed

- Corrected the notice: historical `kernels/rc1.c` is NOT included in this package.
- Documented the actual shipped reference, selected and alternate hash kernels.
- Clarified that TNN-derived AVX-512 ChaCha code is called by the selected kernel
  on supported CPUs; retained all upstream license and copyright notices.
- Added `ATTRIBUTION.json` and eight release-inventory regression tests.
- Updated edition metadata and integrity manifests; updated the website FAQ to
  “What do our recorded tests show?” without changing the recorded measurements.

The native hashing sources, runtime, pool handling, topology, fee schedule and
fee destination are byte-identical to Preview 1. The small Python changes are
edition labels only. No private configuration, wallet keys or workstation binary
is included. Run as a normal user on authorized hardware only.

## Download the named package

Use `OverXelis-Miner-1.0.0-beta.2-public-source-preview.2.tar.gz` with
`SHA256SUMS-public-source-preview.2.txt`, not GitHub's automatic repository ZIP.
Verify the checksum before extracting. The website guide is at:
https://froghollowfirewood.github.io/overxelis-miner/guide.html

SHA-256: `2f0e922007fc6a2fe2c36ad7d1c1cb3f69438ae08f1435d26ae93417ac29b847`

## Final partial-validation update — 29 October 2026 UTC

**The maintainer intentionally ended this run early. The planned 24-hour
stability test was NOT completed.** The observer ran from 12:36:01.587 to
15:31:52.151 UTC: 10,550.559 seconds, or approximately 2 h 55 min 51 s.
The actual stop request was at 15:31:46.136 UTC; native workers closed at
15:31:47.140 UTC. The CLI returned 130 for the handled interruption, with no
fatal log message or forced termination recorded. Both original processes were
absent and their locks were released when checked afterward.

The unchanged exact public package passed its native build, public CLI self-test
and 1,031-input qualification across four C implementations with full scratchpad
comparisons and saved Rust-reference answers. Its separate 180-second ordinary-
memory test completed normally with 23 accepted USER shares. In the subsequent
192-worker huge-page run, the final display reported **110.342 kH/s** gross
session average, **1,193 accepted USER shares**, **6 accepted FEE shares**, and
zero reported rejected or unresolved submissions.

One real USER → FEE → USER cycle was observed: developer authorization, six
accepted FEE shares, return to USER authorization and renewed accepted USER
work. It logged 60.029303 seconds between fee-start and fee-end messages and
59.243 FEE-active seconds. Final USER-active time was 10,484.358 seconds.
No fee window was skipped; no USER connection-interruption message was recorded.
Highest sampled temperature: 72.375 C against the existing 85 C test cutoff.
That cutoff is a test policy, not a hardware certification.

The original `live_smoke_passed: false` and
`full_24h_observation_completed: false` values remain intact. The smoke predicate
requires an ordinary zero-code completion without a stop request; its false
value does not erase the recorded accepted work or imply an unexplained crash.
The original logs and all earlier evidence are preserved.

This is **partial functional validation on one machine**, not an all-day
stability pass, repeated-cycle qualification, comprehensive security review or
matched speed/earnings result. USER and FEE used the same maintainer wallet with
distinct workers; separate-wallet payouts were not independently verified.
GPU mining and desktop activity continued. The historical 110.615 kH/s comparison
reference, source archives, tags, checksums and packaged VALIDATION.json have not
been changed. The package remains experimental Public Source Preview 2.

Final sanitized record:
https://froghollowfirewood.github.io/overxelis-miner/evidence/preview2-early-ended-validation-20261029.json

## Historical checkpoint — 29 October 2026 at 12:38 UTC (superseded above)

The exact published Preview 2 archive subsequently passed a normal-user native
build, the 1,031-input/four-implementation qualification and the public CLI
self-test. Its 180-second ordinary-memory run ended cleanly with 23 accepted
user shares and no rejected or unresolved submissions. A later normal-user
192/192 huge-page session authorized and produced accepted user work.

At that earlier checkpoint a bounded 24-hour observation was running; it was NOT
a completed 24-hour or full real fee-cycle result. The final early-stop record
above supersedes the running status without altering the original evidence. The real 5,940-active-user-
second fee schedule is unchanged. All observed performance is descriptive,
not a matched benchmark. Both test roles use the maintainer wallet with distinct
worker labels. Existing source archives and their packaging-time VALIDATION.json
are unchanged. Detailed dated record:
https://froghollowfirewood.github.io/overxelis-miner/evidence/preview2-runtime-validation-20261029.json

## Validation at release preparation (historical)

62 offline tests passed from the exact new archive: 21 public-package tests,
33 fee/transport tests, and eight release-inventory checks. These tests use
mocks where stated and do not establish a native build or live-pool performance.
The native build safety gate refused while another CPU miner was active; no
existing miner was stopped and no guard was bypassed. Public native build,
1,031-vector native qualification, live-pool operation, a complete real fee
cycle, and prolonged reliability were open at packaging time. Subsequent
evidence is separated in the dated post-release checkpoint above.

## Disclosed developer fee

99 active USER minutes precede a developer window of up to 60 seconds including
connection setup. Failed fee connections are skipped; no catch-up debt. Restart
resets this beta's schedule. It is mining-time allocation, not a wallet
withdrawal or an exact percentage of coins. The existing developer pool/address
are documented in the source and guide. User-accepted work and fee time matter
more than raw share counts or startup peaks.

## Preserved history and known limits

The Preview 1 release, tag, archive and checksum are not replaced. Private rig
successes do not automatically validate the public package. There is no Windows,
macOS, ARM or GPU download. The duplicate-input cache stops at 32,768 entries.
The website and source review are not a security certification or a universal
performance claim. Never provide a seed phrase, private key or exchange login.
