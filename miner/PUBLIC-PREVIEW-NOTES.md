# Public source packaging notes — beta.4 / public-source-preview.2

Source archive: `OverXelis-Miner-1.0.0-beta.4-public-source-preview.2.tar.gz`.
Checksum file: `SHA256SUMS-beta.4-public-source-preview.2.txt`.

This source-only prerelease supersedes preview 1 because that build can stop on
an integer division-by-zero fault. Historical preview-1 archives and checksums
remain unchanged for auditability. Use preview 2 for the selected-kernel fix.

The package contains source, retained public correctness vectors and license
notices. No native binary, compiler installation, private config or local raw log
is included. Build on the mining host using the explicit trusted GCC 15 recipe
in README.md; the documented mode is non-PGO with the existing 4,160-byte worker
color stride. Never add fast-math flags.

The selected checked hash API rejects a zero round modulus before division or
final digest generation. The runtime consumes the failed nonce, records a
separate skip count and first-input capture, and continues. It neither submits
nor counts the failed attempt, and it never creates a substitute hash. Reference
and experimental kernels are outside this narrow protection. Legacy void
selected-kernel calls deliberately trap on failure.

The original failing input was not retained, so its zero-result origin remains
unverified. A captured future input is needed for isolated reference replay.
Qualification and performance records must identify the exact source manifest
and compiled library. The release addendum states which checks were completed.
The short GPU-on development hotfix measurements do not establish an hour-long
hotfix run. The earlier GPU-paused hour used the unpatched build.

The disclosed developer time policy and configuration behavior are unchanged.
No 120 kH/s, 140 kH/s, full-fee-cycle or universal stability guarantee is made.
