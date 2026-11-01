# Beta.3 public source preview 1 — preparation boundary

Prepared for validation and acceptance, not an assertion of completed acceptance.
Selected starting edition: `development-preview.22`.
Selected source-manifest SHA-256: `485e03193411ba6ca10c762c9647ee7f25b196afa937fabf090b8d1c84549ba6`.
All source C, header and assembly bytes are preserved, as are actual build flags
and build logic. The only build-script edit is the packaging_revision string;
the only public_common.py edit is EDITION. VERSION remains 1.0.0-beta.3.

The existing generic configuration is preserved byte for byte. The explicit
optional 7995WX profile requests 192 threads, hugetlb and automatic CPU order;
its wallet placeholder is invalid. Fee destinations and schedule, reference
share verification, protocol behavior and foreground stopping are preserved.

## Validation plan for this exact public package

Use explicit GCC14 and the normal non-PGO build. Then run full 1,031-case,
four-C-implementation hash and entire-scratchpad qualification, public self-test,
all 124 production Python tests and the separate 15 proposal tests. One added
benchmark regression verifies interruption immediately after process ownership is
committed; the corresponding utility patch blocks control signals across child
spawn/assignment and restores inherited masks. It does not change native work or
previous benchmark records. The three new pure profile tests check the optional profile, strict placeholder rejection and
safe shape validation without native hashing, networking or topology reads.

The selected development tree's qualification does not qualify a newly built
public artifact. Each public build must pass its own checks. On the 7995WX,
record sustained comparable performance, pool acceptance, reconnect behavior
and a genuine 99-active-user-minute/60-second fee transition. The historical
110.615 kH/s target and a matched 5% BzMiner advantage are goals, not claims.
Completed measurements and acceptance results belong in the external development
kit report. This archive does not embed mutable measurements or credentials.

## Preserved native file identities

- `experiments/dispatch_round_specialized.c`: `13b1ba601cda3c4d5c7ca90cfee15f128efcd36e15b73d92d4e3436a0ab6c80e`
- `experiments/runtime-topology-colored-huge.c`: `78bab73ae83e08c0f83490eebf26ec8d1065f86913eb72866e11b23e5902ccf8`
- `include/runtime.h`: `27f099f56f5b8550a38a45c806b68e0aef77100191e222d94138b4eefc2ddce9`
- `kernels/experimental.c`: `41e32523bef7f44ddca1dc60e69ba673e6316df194204342aa21ccdeb72120a5`
- `kernels/experimental_arithmetic.h`: `a1699c63e3567e19ed5beb02d80d82e48201b53d98d69dbba629860b086ede4c`
- `kernels/experimental_sqrt.c`: `d3dd0d4ea48a1fd66e68befb1765aeb7c2067dc72074869db519d45617652647`
- `vendor/BLAKE3/c/blake3.c`: `aa8c1a48f80f28399bc050231f5cf7c36bffb77541efa16ee8bfca43d06821e6`
- `vendor/BLAKE3/c/blake3.h`: `c6afa4a206a7edfcd9bcbdbc9432d28c5cca53601ea2d1df9822377a6d74630b`
- `vendor/BLAKE3/c/blake3_avx2_x86-64_unix.S`: `a2d95519fd9845cf80252110e21a93124e81c03da836eaac0bca0537be4f8324`
- `vendor/BLAKE3/c/blake3_avx512_x86-64_unix.S`: `ecf923dc9ccac941b751e7190c9f10b97535d1e8d6e0bb0888a979f5bc0a5fde`
- `vendor/BLAKE3/c/blake3_dispatch.c`: `b12a4d539a8566cec121388e996ed519346ebfa25941d9dc3467a6e8bf3942c4`
- `vendor/BLAKE3/c/blake3_impl.h`: `ae326302ae0403b8f1a5d01d83361e4a87bdd0156ca0b96aecb22eba7d8fa6a0`
- `vendor/BLAKE3/c/blake3_portable.c`: `2bc25b0dad67b4329d0b49cfa075ab2b0d04e424addbddc4e9c389c52a192524`
- `vendor/BLAKE3/c/blake3_sse2_x86-64_unix.S`: `94baa998f4114bf57b99e1791a21e9f0bcdc4bd5803864eb30a2477440b7380c`
- `vendor/BLAKE3/c/blake3_sse41_x86-64_unix.S`: `135048e4a81a6f9e86960b115141874a55954dbfd2cd1e8e9818837b46b498ad`
- `vendor/ChaCha20-SIMD/chacha20.c`: `76b672ca66c5ca06097ff2e2507c1835de1dda8beb80c7cf84e322372c354a4a`
- `vendor/ChaCha20-SIMD/chacha20.h`: `d0d721cddc9a41c93ff42a96f3e1c630da1964d03aefe2c1c9754857e46680d6`
- `vendor/ChaCha20-SIMD/chacha20_avx2.c`: `410ace69c72afcf78dc0ccebaef5cd04c0640603ea4beb4b34fc7a3c86c9335d`
- `vendor/ChaCha20-SIMD/chacha20_dispatch.c`: `d416527cc1ad487f5fba02357d3dca443faa81c8fd8022a1139175543fd03dac`
- `vendor/ChaCha20-SIMD/chacha20_sse2.c`: `b3e232cd9dbc4f546a0213ae3e7523a4224907271b637e4d2c3e51017da0e08f`
- `vendor/ChaCha20-SIMD/cpu_features.c`: `21987607d4ba25a0963a3ce6efb838546b87737ad3bbe8cdd93891afc6a2f6e9`
- `vendor/ChaCha20-SIMD/cpu_features.h`: `9c865c2e68ae49013f65d96d0bf3e35e579c28ba740861641326e27f22039678`
- `vendor/tnn_chacha8_fourstream_wide.h`: `e07581f1552976f0d94da783212c8fcdb41e84fb1497c5ef97e0267999501b74`
- `vendor/xelis_hash_ref.c`: `1ba4a0947833b29a513773fab7c95f5e3ef81afca62563300f62af81b7c0d1db`
