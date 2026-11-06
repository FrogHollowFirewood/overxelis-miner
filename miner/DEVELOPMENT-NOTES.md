# Beta.4 public source preview 2 — validation boundary

This edition preserves the selected beta.4 arithmetic and worker layout while
adding a checked error path for the recorded integer division-by-zero fault.
The native hotfix changes the selected C kernel, worker runtime and runtime
header. Their exact hashes are recorded in VALIDATION.json and the source
manifest. Build with a trusted GCC 15 executable using the normal non-PGO
recipe. Do not change global compiler, power, clock or memory settings as part
of installing this package.

The selected kernel checks each round-end modulus before modular power. A
zero modulus returns failure before digest finalization. Production kernel 1
uses that checked API. Its nonce is already reserved; failure is recorded
separately, excluded from completed-work counts and submission queues, and
followed by the next nonce. A mutex protects the first 112-byte failing-input
capture. Reference/experimental kernels retain their original behavior and the
legacy void selected-kernel entry deliberately traps on failure.

A round-result zero was identified at the historical fault instruction, but
its input was not retained. Whether it was a reference edge case, optimization
error or transient computation fault remains unverified. Replacing a modulus
or inventing a digest would not be a valid repair. Preserve any future captured
input with the source/library identities for isolated reference comparison.

Every local build must pass native self-test and the retained 1,031-input
Rust-answer/four-C/full-scratchpad checks. These replay saved Rust answers;
they do not execute fresh Rust. Retain the manifest, compiler/build record,
library digest, worker-layout report and actual pool evidence. Runtime
regressions must also show nonce consumption, no failed digest submission or
completion count, continued valid work and stable first-input capture.

Development hotfix tests on a 192-thread 7995WX with GPU mining measured
119.303 and 118.955 kH/s over approximately 191 post-settle seconds each,
with 25 and 28 accepted USER shares in the measured windows and zero rejects
or unresolved shares. The release addendum must establish whether an exact
public-package build reproduces that native library. These short observations
do not qualify a one-hour hotfix run or a full scheduled fee transition.
The earlier 121.157 kH/s GPU-paused hour belongs only to the unpatched build.

Existing pool/worker configuration is supplied through --config. Private
settings, raw local logs, compiler wrappers and credentials are not packaged.
The fee schedule, destinations, protocol behavior and foreground Ctrl+C stop
behavior are unchanged. Historical releases retain their original identities
and evidence scopes rather than being relabeled as hotfix qualification.
