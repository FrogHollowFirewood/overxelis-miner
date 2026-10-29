# OverXelis Miner

Independent XELIS CPU-mining software. **1.0.0-beta.2 / public-source-preview.2**

This is an experimental Linux x86-64 source preview for volunteer testers. It has
a configurable public payout address, pool, worker, threads, and memory mode,
and a clearly disclosed 1% scheduled developer mining-time allocation.

The new public packaging has offline checks, not a completed live qualification.
Private beta builds have produced pool-accepted work on 192-, 32-, and 24-thread
systems. That is not proof of this exact public launcher, every CPU, long-term
stability, or a matched 5% advantage over another miner.

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
checksum from the new prerelease. Native build/qualification and live-pool/fee-
cycle validation of the public package remain pending. Offline tests are not
proof of those results. See [the correction notes](miner/PUBLIC-PREVIEW-NOTES.md).
