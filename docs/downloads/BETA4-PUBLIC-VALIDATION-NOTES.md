# Beta.4 public validation addendum · 6 November 2026

This note accompanies **OverXelis Miner 1.0.0-beta.4 / public-source-preview.1**.
It updates the interpretation of the frozen archive's preparation documents;
it does not change any source file or the archive checksum.

## Read this before the internal validation descriptor

The archive's README, CHANGELOG, PUBLIC-PREVIEW-NOTES and VALIDATION.json preserve
an **earlier development checkpoint**. In particular, VALIDATION.json names an
earlier selected-kernel hash (`f10c075b…`) and development source (`75ddabf5…`),
and describes an earlier 118 kH/s acceptance plan. Those entries do **not**
identify the final selected C file or establish its current validation result.
The GCC 15/192-worker wording there describes the desktop development profile;
GCC 13.3 and GCC 11.4 later passed local correctness and pool startup on other rigs.

The current source manifest and dated evidence below **supersede those earlier
validation descriptions and hash references**. The earlier text remains in the
archive to preserve the exact source package that was built and qualified.
Do not regenerate its manifest or edit source files to make the documents agree.
DEVELOPMENT-NOTES also mentions STAGING-METADATA; that development-side record
is not shipped and is not required to build or run this source preview.

## Exact source and tested desktop identities

| Item | SHA-256 |
| --- | --- |
| Source archive, 309,121 bytes | `7c0e9bf745d22c86bf186e360ed2a8cc23ec5bdb7e188adf4fd1c7a4a24c5cd4` |
| SOURCE-MANIFEST.json, 68 tracked source files | `90ca3e0d6485140a149b06f3dc14c4cfdf873e7e903d22440ac3c9c8f19a9bcc` |
| Actual selected experiments/dispatch_round_specialized.c | `6c76ff348eae2bfdf99aac24ba576641310a3576585c796f9f21fc0b1c43b4b1` |
| Tested desktop build/liboverxelis.so | `f5072ba1737ce1719826f1a8aac022e1d0c675cd5f71ee3f6204941bedc599e5` |
| Tested desktop build/build.json | `f5e1d5822b71b033d462bb2d37f836677467dd8094f5a9e870291ef3a6f236d9` |
| Tested desktop kernel-qualification.json | `37446beabd940680a26f497f3ac159aa23a377d7a5a4a0bdac5f12cba8609323` |

The archive contains exactly 69 regular files: 68 tracked source files and their
manifest. It contains no native library, live configuration or mining logs.
The desktop native/build identities above are evidence references, not files
included in the source archive. Every local build has its own identities; do
not copy a desktop `-march=native` library to a different computer.

## Current validation and its limits

**One Threadripper PRO 7995WX desktop, 192 hugetlb workers, GCC 15.2.0, ordinary
non-PGO build, GPU mining paused and all six fan channels on Mining100** recorded
366 counted Local samples after 600 seconds of settling. Their unweighted mean
was **121.157224 kH/s**, with a **120.908 kH/s minimum**. Conservative post-settle
active USER coverage was 3,671.545 seconds, with 393 accepted USER shares and
zero rejected or unresolved work. CPU clock/voltage settings were unchanged.
No counted pause, reconnect or error was recorded, and normal cleanup completed.

Those are rounded displayed Local rates, not an independent raw-counter hour
rate, pool-side estimate or earnings measurement. A separate GPU-on attempt
did not pass the strict displayed 120 kH/s minimum. The passing result applies
to the GPU-paused/cooling conditions stated above.

Separate real Kryptex runs on that same desktop artifact and conditions measured
23.844454 kH/s with 24 workers over 311.380 seconds and 31.786244 kH/s with 32 workers
over 311.512 seconds, using completed-hash counts after at least 60 seconds of
settling. The measured intervals accepted 3 and 13 USER shares respectively,
with zero rejected/unresolved work. These are shorter desktop profiles, not
one-hour results or measurements of the separate CPU rigs.

Three other rigs locally rebuilt this source at 32/24/24 workers with
GCC 13.3.0/13.3.0/11.4.0, passed the full correctness and actual huge-page worker
checks, and verified accepted Kryptex USER startup work. Existing configuration
and service policies were preserved, with no GPU changes reported. No sustained
rate or desktop 120 kH/s result is claimed for those rigs.

No completed beta.4 fee cycle, deliberate live reconnect-recovery test, universal
fastest setting or matched 5% advantage over BzMiner is established. Earlier
beta.3/beta.2 results remain historical observations under their own conditions.

## Build and run the source preview

Use Linux x86-64 with AES-NI, Python 3.10+ and GNU binutils. The recorded desktop
profile used an existing trusted GCC 15.2 executable and no PGO. GCC 13.3 and 11.4
also passed on the other hosts described above; every compiler/CPU combination
still requires local correctness qualification. No compiler download or system
package installation is performed by the source package.

Stop an existing CPU miner normally before building or qualifying. Build as a
normal user on the computer that will mine. Preserve strict binary64 behavior;
do not add `-ffast-math`. The following is the ordinary correctness-then-pool
workflow, with no offline throughput benchmark.

Download the named source archive and its matching checksum into one directory:

```bash
sha256sum --check SHA256SUMS-beta.4-public-source-preview.1.txt &&
tar -xzf OverXelis-Miner-1.0.0-beta.4-public-source-preview.1.tar.gz &&
cd OverXelis-Miner-1.0.0-beta.4-public-source-preview.1
```

Replace the compiler placeholder with the absolute path of your existing trusted
GCC. Use GCC 15.2 to follow the recorded desktop compiler profile:

```bash
python3 -I -B build_public.py --compiler /absolute/path/to/gcc15 &&
python3 -I -B qualify_public.py &&
bash run.sh --self-test
```

Stop on any failure. Full qualification replays 1,031 retained Rust-answer inputs
through four C implementations and compares entire reference scratchpads; it
does not rerun Rust. Preserve build/build.json and the qualification record.
Use a fresh verified source directory for a new build; existing output is not
overwritten. If using hugetlb, additionally run tools/qualify_worker_layout.py
at the intended thread count before mining. Huge pages and permissions must
already be configured; no silent memory-mode fallback is allowed.

For a **new configuration**, choose a new private file path:

```bash
bash run.sh --config /absolute/path/to/private-config.json --configure
```

The wizard starts no mining and refuses to overwrite an existing file. For a
new or existing configuration, review and check it before starting real pool work:

```bash
bash run.sh --config /absolute/path/to/private-config.json --check &&
bash run.sh --config /absolute/path/to/private-config.json --accept-dev-fee
```

Use your public payout address and compatible pool/worker settings; no private
key or seed phrase is needed. The public examples contain invalid payout
placeholders. Press Ctrl+C to stop. The disclosed 1% developer mining-time policy
is unchanged: 99 active USER minutes, then a FEE window of up to 60 seconds.
This schedule does not promise an exact percentage of coins or profit.

## Dated public evidence

- [Sanitized beta.4 evidence](https://github.com/FrogHollowFirewood/overxelis-miner/blob/main/docs/evidence/beta4-validation-20261106.json)
- [Project README](https://github.com/FrogHollowFirewood/overxelis-miner/blob/main/README.md)
- [Release notes and preserved history](https://github.com/FrogHollowFirewood/overxelis-miner/blob/main/RELEASE-NOTES.md)
- [Website validation report](https://froghollowfirewood.github.io/overxelis-miner/site-status.html#beta4-validation)

The dated report identifies the exact source, tested desktop build and separate
rig builds. It contains sanitized observations rather than private configuration,
raw mining logs or user credentials. Checksums detect unexpected file changes;
they are not publisher signatures.
