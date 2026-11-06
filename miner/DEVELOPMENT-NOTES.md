# Beta.4 public source preview 1 - validation boundary

The documented selection is the revised selected C kernel with the original
runtime (4,160-byte worker color stride), built using explicit GCC 15 and the
normal non-PGO recipe. README.md provides the operational commands and
CHANGELOG.md describes the source changes.

The selected development source is `tail-lab/c2-sqrt-probability/c2_sqrt_probability.c`, SHA256
`75ddabf5cc45d5d861fd90b69af4b527a05e631d91bb4d746ad0d017545c5a9c`.
Two C2 products use the local readonly constant as an explicit memory operand
to low64 IMUL. Two existing root-guard comparisons gain compiler probability
annotations. The products remain exact modulo 2^64; the annotations preserve
guards, fallback corrections and wrapping cases. Their model probability is
not an observed input distribution. All existing scratch operations remain
unchanged. STAGING-METADATA.json records the preserved C body and the virtual
header-replaced source identities.

Each final build requires its own native self-test, 1,031 saved-answer/four-C/
full-scratchpad qualification and actual hugetlb worker-layout check. Saved
Rust answers are replayed; Rust is not rerun by those checks. Keep the source
manifest, compiler/build record, library digest and all qualification reports.

Sustained performance and a one-hour live-pool test require final-artifact
evidence, including measured duration, rate samples, accepted/rejected counts,
reconnects and test conditions. The proposed evidence locations in README.md
are not assertions that those checks passed. Final acceptance requires actual
hugetlb qualification at 192, 32 and 24 workers, three matched 60-second
192-worker comparison pairs, at least 118 kH/s sustained independent-counter
throughput, 300 measured seconds each at 24/32 workers after 30-second warmups,
and at least 3,660 post-settle live-pool seconds. Use the existing soak option
`--measure-seconds 3660` with at least 120 seconds of settling; review its actual
active-time proof. VALIDATION.json describes requirements and evidence
references; completed reports belong in the exact build evidence and the
development kit validation-evidence/. A one-hour run does not exercise
the first fee transition, which follows 99 active USER minutes.

Existing pool/worker configuration is supplied with `--config` and read by
the check and mining commands. It is not redistributed or rewritten as part
of packaging. Fee schedule/destinations, protocol behavior and foreground
stopping retain their existing behavior.

Historical beta.3 records retain their original version, identities and scope.
They provide provenance, not qualification of a new beta.4 artifact.

