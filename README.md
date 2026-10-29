# OverXelis Miner

Independent XELIS CPU-mining software. **1.0.0-beta.2 / public-source-preview.2**

This is an experimental Linux x86-64 source preview for volunteer testers. It has
a configurable public payout address, pool, worker, threads, and memory mode,
and a clearly disclosed 1% scheduled developer mining-time allocation.

The exact public Preview 2 archive passed a normal-user native build and
1,031-input correctness qualification, then produced pool-accepted work and one
real USER → FEE → USER transition on one 192-thread Linux desktop. The maintainer
ended the huge-page observation early after **2 hours 55 minutes 51 seconds**.
**The planned 24-hour stability test was not completed.** See the
[final partial-validation report](docs/site-status.html#runtime-validation) and
[sanitized evidence](docs/evidence/preview2-early-ended-validation-20261029.json).

The final display reported 110.342 kH/s gross session average, 1,193 accepted
USER shares and 6 accepted FEE shares, with zero reported rejected or unresolved
submissions. The requested interrupt returned code 130 and closed native workers.
These are limited functional observations, not a matched speed comparison,
net earnings result, security certification, or evidence of extended stability.
Private 32/24-thread observations do not automatically establish this public
package on those systems. None of these checks proves a matched speed advantage.

Read [the complete guide](miner/README.md), [validation status](miner/VALIDATION.json),
[packaging notes](miner/PUBLIC-PREVIEW-NOTES.md), and [security information](miner/SECURITY.md).
Download the **public source preview** from the tagged prerelease, not a private rig installer.

The project website is in `docs/`. It does not mine in browsers, accept payments,
collect configuration fields, or install software automatically. `miner/` contains
the auditable source; no private user settings or precompiled workstation binary
is supplied. Run only on computers you own or are authorized to use.

OverXelis is not affiliated with or endorsed by XELIS or Kryptex. Project code is
MIT licensed; third-party components retain their included notices and licenses.

## Preview 2 correction

This edition corrects shipped-file attribution and adds release-inventory checks.
It does not change hashing code, pool handling, or the 1% mining-time policy.
Preview 1 is retained unchanged; use the separately named Preview 2 archive and
checksum from the new prerelease. The archive’s VALIDATION.json is the
packaging-time snapshot; separate dated records add subsequent native and live
evidence, including one real fee transition and the intentional early stop.
Repeated-cycle reliability and 24-hour stability remain unverified. See [the correction notes](miner/PUBLIC-PREVIEW-NOTES.md).
