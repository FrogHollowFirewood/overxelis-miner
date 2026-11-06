# Beta.4 public source preview 2 — hotfix validation notes

Date: November 6, 2026. This addendum accompanies the source-only hotfix
`1.0.0-beta.4 / public-source-preview.2`. It supersedes preview 1 for current
downloads. Preview 1's original archives, checksums and historical evidence are
preserved.

## Public package identity

- Archive: `OverXelis-Miner-1.0.0-beta.4-public-source-preview.2.tar.gz`
- Archive size: **314,326 bytes**
- Archive SHA-256: `4ede37b957b5024611f63714f4593bd60a849c0dd9c14594490353c56bdb53da`
- Source-manifest SHA-256: `3bcc699a8e7252584b2b0df15a0943b9299b35b4ba0c48e32982f9eb555f2b5e`
- Inventory: **69 manifest-tracked source files plus the manifest, 70 regular files total**
- Checksum file: `SHA256SUMS-beta.4-public-source-preview.2.txt`

No compiled miner, compiler installation or private user configuration is
included. Use the named archive and its matching checksum. A checksum detects
unexpected changes; it is not a publisher signature.

## Exact public-package qualification

**PASSED on November 6, 2026, at 19:44:18 UTC.** The exact named archive was verified and extracted into a fresh directory. Its normal GCC 15.2 build passed the native self-test, 1,031 saved Rust-answer inputs through four C implementations, and 1,031 full-scratchpad comparisons. Rust itself was not rerun. All 192 actual hugetlb workers produced reference-verified terminal hashes with zero dropped shares.

The packaged forced-zero reproducer also passed at 1, 24, 32 and 192 hugetlb workers. Every deliberately failed nonce was consumed without incrementing completed work or queuing a share; the first failing input was retained in runtime memory and single-hash output remained untouched. The production sources, objects and library remained unchanged. The test library is a separate deliberately failing artifact and is not distributed as a miner.

Exact-package native-library SHA-256: `e519d8b10619776a16db50252f41b0fd70f300d0e2b05633577249cc9874faa9`.

Exact-package build-record SHA-256: `c255361e0f2b1c5b254932fa1ffdff8c720ed8cc50730690e671a10ed3f2fb7a`.

The rebuilt native library is **byte-for-byte identical** to the development hotfix library used in the two short Kryptex measurements below. This binds those native performance observations to the public source build; it does not claim a fresh live session with preview-2 edition metadata, a new hour test or long-term stability. The changed edition documentation and tests are identified by the public source manifest.

The archive's `VALIDATION.json` describes the hotfix and per-build requirements.
It is a static descriptor, not a completed test report. This separate addendum
and the matching sanitized JSON carry subsequent preparation and test results;
the archive need not be regenerated to insert later observations.

## Recorded fault and repair scope

The earlier beta.4 stopped at an integer division instruction when a round-end
modulus was zero. Linux reported SIGFPE, which the shell displayed as
“floating point exception.” The historical failing input was not retained,
so the origin of that zero result remains unverified.

The hotfix adds a checked path for production selected kernel 1. It detects the
zero modulus before division or digest finalization, consumes that nonce,
records a separate skipped-input count and first failing input, and continues
with later work. A failed attempt is not counted as a completed hash, queued
as a share, or given a substitute digest. Ordinary selected-kernel arithmetic,
worker placement, configuration and the disclosed developer-time policy remain.

This is protection of the recorded selected-kernel failure path. Reference
and experimental kernels remain outside that guard; legacy void selected-kernel
calls deliberately trap on checked failure. The fix does not prove that every
possible SIGFPE is eliminated. Capture and isolated reference replay of a
naturally failing input remain necessary to determine why the historical
round result became zero.

## Source tests and development qualification

The prepared preview-2 source passed **126 local source tests**, including
seven native worker state-machine tests and two checked-failure regressions.
The suite completed in 1.202 seconds. Its runtime tests use deliberately
non-consensus hash stubs; they do not substitute for production hash checks.

The development hotfix used these identities:

| Item | SHA-256 |
| --- | --- |
| Development source manifest | `f38c2e8dbf30c100a81962a0a48f2f8a59a37ccd3fff926b3adbe428a252e9b0` |
| Development native library | `e519d8b10619776a16db50252f41b0fd70f300d0e2b05633577249cc9874faa9` |
| Development build record | `ef603fadb41da647aeff247535020dfb56e86016dc99783623a35163c9f36006` |

That library passed native self-test, replay of **1,031 saved Rust hash answers
through four C implementations**, and **1,031 full-scratchpad comparisons**.
Rust itself was not rerun. Each of 192 actual hugetlb workers completed a
reference-verified terminal hash, with zero dropped shares.

A separate test copy forced the round result to zero immediately before the
new guard. Tests at **1, 24, 32 and 192 workers** consumed one terminal nonce per
worker, recorded the expected skipped counts and first-input capture, and
produced zero completed hashes or queued shares. These are deliberate
correctness failures, not throughput measurements or naturally reproduced
instances of the historical crash. The newly packaged reproducer was also executed successfully for the exact public package, as recorded above.

## Two short Kryptex measurements

Both development-hotfix runs used an AMD Threadripper PRO 7995WX, **192
hugetlb workers**, GCC **15.2**, ordinary non-PGO compilation and **GPU mining
running**. Each run
had a separate process and settling period; the windows are not one continuous
longer test.

| Measurement | Window 1 | Window 2 |
| --- | ---: | ---: |
| Settling before measurement | 60.362 s | 60.244 s |
| Measured duration | 191.064 s | 190.778 s |
| Completed hashes | 22,794,482 | 22,694,011 |
| Gross local completed-work rate | **119.303 kH/s** | **118.955 kH/s** |
| Accepted USER shares within window | 25 | 28 |

The full sessions ran for approximately 270 seconds and recorded 31 and 44
accepted USER shares respectively, with zero rejected or unresolved shares.
At native close, both recorded zero queue drops, zero skipped undefined
inputs and no captured bad input. Thus the live runs establish short normal
pool operation, while the deliberate test copy exercises the failure path.
The exact counter boundaries and UTC session times are in the sanitized JSON.

Rates count locally completed work, including work invalidated by a later job
change. They are not pool-side hashrate estimates, payouts or earnings. Share
discovery varies randomly, so accepted-share counts are separate observations.

## Remaining limits

- **No one-hour or longer soak result is established for this hotfix package.**
- The earlier **121.157 kH/s GPU-paused hour** used unpatched beta.4. It remains
  historical evidence and does not qualify this hotfix.
- A full scheduled developer-fee transition and deliberate live reconnect
  recovery are not qualified by these short runs.
- Results on other CPUs, compiler builds and memory/worker profiles require
  their own qualification. Forced checks at 24/32 workers are not measured
  24/32-worker mining rates for this package.
- There is no guaranteed **120 kH/s**, no demonstrated **140 kH/s beta.5**
  result, and no established matched ranking against another miner.

Build locally using the GCC 15 recipe in the archive, run its correctness
checks, and retain matching source/build/library identities. Stop an existing
CPU miner normally before building, qualifying or launching another instance.
The source package installs no automatic mining service.
