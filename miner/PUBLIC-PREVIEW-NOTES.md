# Public source packaging notes - 1.0.0-beta.4 / public-source-preview.1

Source archive: `OverXelis-Miner-1.0.0-beta.4-public-source-preview.1.tar.gz`.
Checksum file: `SHA256SUMS-beta.4-public-source-preview.1.txt`.

This edition contains source, retained public test vectors and license notices.
It includes no compiled native binary, compiler installation or private user
configuration. Build on the mining host using the explicit GCC 15 recipe in
README.md. The documented selection is non-PGO with the original runtime and
its 4,160-byte worker color stride.

The selected kernel's release header describes its role and attribution;
historical experiment labels have been removed from that header. Header
replacement must leave all bytes from `#define _GNU_SOURCE` onward unchanged
relative to the selected, qualified kernel.

Correctness, performance and pool-operation evidence must identify this exact
source manifest and resulting library. See README.md for kernel qualification,
worker-layout qualification and the expected sustained-screen/hour-test records.
No completed 118 kH/s, one-hour or fee-cycle result is asserted by this note.
Beta.3 labels in retained historical records must not be rewritten as beta.4.

