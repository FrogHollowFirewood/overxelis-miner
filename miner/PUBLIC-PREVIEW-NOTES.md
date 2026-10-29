# Public packaging notes — 1.0.0-beta.2 / public-source-preview.2

This is a separately versioned attribution/documentation correction to preview 1.
The existing preview-1 release, tag, source archive and checksum are preserved.
New asset: OverXelis-Miner-1.0.0-beta.2-public-source-preview.2.tar.gz.
The matching checksum file is SHA256SUMS-public-source-preview.2.txt.

## Changes

- Correct the erroneous claim that historical kernels/rc1.c is shipped.
- Identify the actual shipped reference, selected and alternate hash sources.
- Clarify that the TNN-derived ChaCha path is used by the selected kernel on
  supported CPUs, not just by comparison code; retain upstream licenses.
- Add a machine-readable attribution inventory and packaging regression tests.
- Update edition labels, package names, documentation and source-manifest hashes.

No hashing C/header/assembly code, pool protocol, worker runtime, fee schedule,
fee destination, topology selection or user mining configuration is changed.
The public_common.py and build_public.py changes are edition metadata only.
This is not a speed optimization, stable release, or automatic miner update.

## Validation boundary

Offline tests are run against the exact new archive before publication. The
native build, native qualification, live-pool operation and complete real fee
cycle remain unverified for this public edition; the build safety gate refused
while another CPU miner was active. That guard was not bypassed and no running
miner was stopped. A future test must use an idle authorized target machine.
Passing private-rig tests and mock fee tests does not fill these public-package
gaps. See VALIDATION.json and the release review for the actual test scope.

For a clean future validation, verify and extract this archive, then run the
published build, qualification and self-test commands before a deliberate pool
test. A complete fee cycle needs 99 active user minutes before its first fee
window, followed by resumed USER mining. No shortened production fee cycle is
substituted for that check. Preserve logs; do not bypass a failed gate.
