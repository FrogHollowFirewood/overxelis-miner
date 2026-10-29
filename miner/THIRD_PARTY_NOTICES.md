# Source attribution

The new worker runtime, Python pool client, topology code, measurement tools,
and their tests are authored for this project. They are independent new code.
That does not establish a world-first invention or a performance improvement.

The consensus hash must match XelisHashV3 exactly. Reused hashing and crypto
components are explicitly retained, rather than described as new inventions:

* `vendor/xelis_hash_ref.c`: adapted from the Xelis project's C reference at
  commit `f48262b931438fdbf2932711613e020c02f1ea04`. The standalone reference
  benchmark/main was removed and unused sodium initialization was replaced.
  Condition-code clobbers were added to its x86 division/rotation assembly to
  accurately describe those instructions to the compiler. No arithmetic
  operation changed. See `vendor/XELIS-LICENSE` (MIT).
* `vendor/ChaCha20-SIMD`: carried forward from the pinned reference's dependency
  tree. See its `LICENSE`. Earlier research fixed function prototypes and
  unsigned feature masks; these changes are preserved. This project additionally
  makes AVX2 dispatch check OS vector-state support through compiler built-ins.
* `vendor/BLAKE3`: carried forward from the pinned reference's dependency tree.
  See `LICENSE_CC0` and `LICENSE_A2`. The selected Unix assembly files have
  applicable notices retained.
* `vendor/tnn_chacha8_fourstream_wide.h`: previous JayXelis/TNN-derived
  four-stream AVX-512 stage, carried forward as the comparison implementation.
  See `vendor/TNN-LICENSE`. No new invention is claimed for this code.
* `kernels/rc1.c`: prior JayXelis implementation, derived from the MIT Xelis
  reference and the dependencies above. Kept as a control kernel.
* `kernels/experimental.c`: new research modifications to the control kernel.
  See its comments and experiment ledger for the exact changes.

Upstream: https://github.com/xelis-project/xelis-hash
Pinned revision: https://github.com/xelis-project/xelis-hash/tree/f48262b931438fdbf2932711613e020c02f1ea04

Only Linux x86-64 with AES-NI is supported by this prototype. Optional AVX-512
code has runtime dispatch; AVX-512 fallback is not proof of support on other
architectures. No proprietary SRBMiner code is used.
