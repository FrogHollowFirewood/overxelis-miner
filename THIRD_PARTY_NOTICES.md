# Third-party attribution

The current public miner's complete shipped-file attribution is in
[miner/THIRD_PARTY_NOTICES.md](miner/THIRD_PARTY_NOTICES.md), with a machine-readable
inventory in [miner/ATTRIBUTION.json](miner/ATTRIBUTION.json).

Paths in that document are relative to the miner package root, not this
repository root. It identifies the XELIS-derived selected/reference kernels,
TNN-derived conditional ChaCha path, BLAKE3 and ChaCha20-SIMD dependencies,
and the retained license files. Historical development artifacts are separately
marked as not shipped. No upstream endorsement or original invention of all
components is claimed.

Public Source Preview 2 corrects Preview 1's inaccurate statement that historical
kernels/rc1.c was included, and clarifies actual use of the TNN-derived code.
The old release's tag and download remain unchanged for traceability.
