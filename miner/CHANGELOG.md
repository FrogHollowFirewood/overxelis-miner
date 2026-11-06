# Release history

## 1.0.0-beta.4 · public-source-preview.2

Supersedes preview 1 with a checked selected-kernel path for the recorded
integer division-by-zero fault. A zero round modulus is rejected before division
or digest finalization. The runtime consumes the nonce, records a separate skip
count and first-input capture, excludes failed attempts from completed-work
counts and submission queues, and continues with valid work. Ordinary selected
hash arithmetic, worker layout, configuration and disclosed fee policy remain.

The historical failing input is unavailable; the origin of its zero round
result remains unverified. Reference and experimental kernels are outside this
narrow guard; legacy void selected-kernel calls deliberately trap on failure.
New native runtime regressions cover failure accounting, nonce consumption and
continued valid work. README.md and VALIDATION.json state the exact build and
evidence boundaries. Short hotfix pool tests are not a completed hour-long
hotfix qualification or a performance guarantee.

## 1.0.0-beta.4 · public-source-preview.1

Historical and superseded by preview 2 because the selected kernel can stop on
a zero-modulus integer division. Its original artifacts and evidence remain unchanged.

This source edition carries a revised selected XelisHashV3 CPU kernel and a
GCC 15 non-PGO build recipe. The selected kernel uses shared tails for the
cheap arithmetic cases, packed square-root estimates with exact correction,
guarded fast correction with an unchanged wrapping fallback, reused index
folds, and unconditional two-DIV normalization for the consumed quotient and
remainder words. It preserves consensus-visible hash and scratchpad behavior.

The original runtime remains selected, including its 4,160-byte worker color
stride. The foreground CLI, existing pool/worker configuration format, explicit
`--accept-dev-fee` acknowledgement and 5,940-active-USER/60-FEE policy remain.

Native qualification checks 1,031 saved Rust answers through four C
implementations and full scratchpads. Actual worker-layout, sustained-rate
and hour-test results must identify the final source and library. This entry
does not assert 118 kH/s, a completed one-hour run, or a completed fee cycle.

## 1.0.0-beta.3 · public-source-preview.1

Historical source preview used as the beta.4 starting point. It included the
round-specialized kernel, explicit GCC 14 build selection, disclosed developer
time policy, retained reference corpus and optional 7995WX profile. Its version,
source identities and historical acceptance statements belong to that edition;
they are not beta.4 qualification evidence.

