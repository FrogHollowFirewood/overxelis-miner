# Release history

## 1.0.0-beta.5 · public-source-preview.1

- Selects the checked beta.5 development kernel with revised Stage 3 addressing.
- Prepares compatible standby connections for USER/FEE handoffs. Standby jobs
  stay idle until activation. The 99-minute USER and up-to-60-second FEE
  schedule is retained.
- Includes the beta.5 trial's selected source and public version metadata.
  The separate Stage 3 split-store experiment remains under qualification.

## 1.0.0-beta.4 · public-source-preview.1

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

