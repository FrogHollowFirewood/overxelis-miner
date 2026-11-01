# Public source packaging notes — 1.0.0-beta.3 / public-source-preview.1

Source archive: `OverXelis-Miner-1.0.0-beta.3-public-source-preview.1.tar.gz`.
Checksum file: `SHA256SUMS-beta.3-public-source-preview.1.txt`.

Prepared for validation and acceptance from one frozen qualified development
source. All C, header and assembly files, actual build flags and build logic are
preserved. Changes are public edition metadata, documentation, metadata tests,
an optional 7995WX placeholder configuration with three pure profile tests, and
one precise benchmark child-ownership signal-window correction with one regression
test. The utility fix changes no native code, build flags or mining logic.
The generic configuration and mining, fee, topology and protocol logic are unchanged.

Use explicit GCC14 and an ordinary non-PGO build as described in README.md.
No completed performance, live-pool or full real fee-cycle success is claimed.
The separate development-kit report owns completed measurements and acceptance
status; this source archive remains immutable.
