# Source attribution — public-source-preview.2

This document describes the files shipped in this public source package. Paths
below are relative to the package root (the repository's `miner/` directory).
The project includes XELIS-derived hashing code and third-party cryptography;
it does not claim that every component is independently invented or that source
availability establishes correctness, security, or a performance advantage.
All existing copyright notices and license texts remain in the package.

## Shipped hashing and cryptographic components

* `vendor/xelis_hash_ref.c` is the adapted XelisHashV3 C reference, used by the
  qualification checks. Its retained provenance identifies XELIS revision
  `f48262b931438fdbf2932711613e020c02f1ea04`. Prior adaptations removed the
  standalone benchmark/main and unused sodium initialization, and added
  condition-code clobbers to x86 division/rotation assembly. See
  `vendor/XELIS-LICENSE` (MIT).
* `experiments/dispatch_round_specialized.c` is the selected hashing
  implementation in this edition. It derives from the XELIS C reference and
  earlier project experiments, rather than constituting a new consensus
  algorithm. The build maps its exported function to `xelis_hash_v3_opt`.
* `kernels/experimental.c` and `kernels/experimental_sqrt.c` are alternate,
  XELIS-reference-derived implementations included in the correctness checks.
  `kernels/experimental_arithmetic.h` supplies their arithmetic helpers.
* `vendor/tnn_chacha8_fourstream_wide.h` adapts TNN's four-stream AVX-512 ChaCha
  path. Its retained header identifies `include/chacha20_xelis_inline.h` at
  TNN revision `b567a87b9fef84e20ebc4b7747ad871361b31974`, copyright 2023
  Tritonn204. See `vendor/TNN-LICENSE` (MIT). This header is included and its
  function is called by the selected round-specialized implementation AND the
  two alternate kernels when the required AVX-512 features are available.
  It is not merely an unused comparison artifact. The source also retains a
  serial fallback for CPUs without those features.
* `vendor/ChaCha20-SIMD/` contains the carried-forward ChaCha implementation,
  CPU-feature detection and dispatch. See `vendor/ChaCha20-SIMD/LICENSE`
  (MIT; copyright 2023 Yury Myakotin). Earlier prototype changes to function
  declarations, feature masks and AVX2 OS-state checks are retained.
* `vendor/BLAKE3/` contains the carried-forward BLAKE3 implementation and
  selected x86-64 assembly sources. The included license options are in
  `vendor/BLAKE3/LICENSE_A2` and `vendor/BLAKE3/LICENSE_CC0`; source notices
  are retained.

## Project-specific integration and qualification

`experiments/runtime-topology-colored-huge.c`, `include/runtime.h`, `miner.py`,
`topology.py`, `overxelis.py`, `overxelis_fee.py`, and `public_common.py` provide
the worker integration, pool protocol, configuration and disclosed fee handling.
The build and qualification entry points are `build_public.py` and
`qualify_public.py`; `tools/kernel_lab.py` supplies qualification helpers.
The retained input/answer corpus is described in
`reference/CORPUS-PROVENANCE.json`. Qualification replays saved Rust answers;
it does not execute a new Rust reference build.

The machine-readable `ATTRIBUTION.json` lists these shipped paths and license
locations. It is an inventory, not an independent legal or originality audit.
Project-specific code is covered by the included project MIT license; upstream
components retain their own notices and applicable licenses.

## Historical development references — not shipped files

An earlier research tree contained a file named `kernels/rc1.c` and additional
experiment generators and ledgers. Those historical artifacts are NOT shipped
in this public source package. Preview 1's notice incorrectly said that rc1.c
was retained as a control kernel; this edition corrects that packaging statement.
The included reference/control for the four-implementation qualification is
`vendor/xelis_hash_ref.c`. Some unchanged source comments describe the files'
earlier experimental status; the build recipe identifies the selected kernel.
This documentation correction does not change the hashing implementation.

Upstream projects: https://github.com/xelis-project/xelis-hash and
https://github.com/Tritonn204/tnn-miner . Retained source identifiers document
provenance; they do not imply endorsement by any upstream developer.

Scope remains Linux x86-64 with AES-NI. Optional AVX-512 dispatch does not imply
support for other architectures. See `VALIDATION.json` for what was actually
checked for this public edition. This notice is not a performance guarantee.
