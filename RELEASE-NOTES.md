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

## Validation, without overclaiming

62 offline tests passed from the exact new archive: 21 public-package tests,
33 fee/transport tests, and eight release-inventory checks. These tests use
mocks where stated and do not establish a native build or live-pool performance.
The native build safety gate refused while another CPU miner was active; no
existing miner was stopped and no guard was bypassed. Public native build,
1,031-vector native qualification, live-pool operation, a complete real fee
cycle, and prolonged reliability remain open for this edition.

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
