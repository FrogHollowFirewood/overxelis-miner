# Public packaging notes — 1.0.0-beta.2 / public-source-preview.1

This edition is deliberately separate from the private desktop/rig installations.
No running installation is changed when the public files are staged or published.

The selected round-specialized hashing source, runtime, consensus reference,
cryptographic dependencies and rig-recovery fee module are copied by explicit
allowlist from the corrected rig r2 source package. Its selected export mapping
and `-fno-crossjumping` build option are retained. No binary compiled on the
maintainer's workstation is distributed.

New packaging consists of a normal-user foreground launcher, configurable wallet,
pool, worker, thread count and page mode, an interactive configuration wizard,
a per-user lock, general-purpose build/qualification entry points, documentation,
and tests. These packaging changes do NOT inherit a claim of full live validation
from the private rig installation. Check `VALIDATION.json` for the precise work
performed for this archive. In particular, the public build/qualification and
full fee cycle must still be exercised on intended target machines.

The source preview is intended for beta feedback; it is not a silent stable
upgrade, performance promotion, or recommendation to replace an existing
production miner. There is no auto-update mechanism.
