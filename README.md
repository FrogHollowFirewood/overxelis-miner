# OverXelis Miner

Independent XELIS CPU-mining software. **1.0.0-beta.4 / public-source-preview.1**

Experimental Linux x86-64 source preview. Build and qualify it on the computer
that will mine. Configure your own public payout address, pool, worker, thread
count, CPU order and memory mode. The disclosed **1% scheduled developer
mining-time allocation** remains unchanged: 99 active USER minutes, followed
by a fee window of up to 60 seconds.

## Beta.4 source download

- **[Download beta.4 source archive](https://github.com/FrogHollowFirewood/overxelis-miner/releases/download/v1.0.0-beta.4-public-preview.1/OverXelis-Miner-1.0.0-beta.4-public-source-preview.1.tar.gz)**
- [Matching SHA-256 checksum](https://github.com/FrogHollowFirewood/overxelis-miner/releases/download/v1.0.0-beta.4-public-preview.1/SHA256SUMS-beta.4-public-source-preview.1.txt)
- [Public validation addendum and current build instructions](https://github.com/FrogHollowFirewood/overxelis-miner/releases/download/v1.0.0-beta.4-public-preview.1/BETA4-PUBLIC-VALIDATION-NOTES.md)
- [Beta.4 release page](https://github.com/FrogHollowFirewood/overxelis-miner/releases/tag/v1.0.0-beta.4-public-preview.1) · [All releases](https://github.com/FrogHollowFirewood/overxelis-miner/releases)
- [Website guide](https://froghollowfirewood.github.io/overxelis-miner/guide.html) · [Current validation report](https://froghollowfirewood.github.io/overxelis-miner/site-status.html#beta4-validation)

Use the named **source-only prerelease** and its matching checksum, rather than
GitHub's automatic repository ZIP. The archive is **309,121 bytes** and contains
68 tracked source files plus their manifest. No precompiled miner, live user
configuration, private deployment kit or mining logs are included.

```text
SHA-256: 7c0e9bf745d22c86bf186e360ed2a8cc23ec5bdb7e188adf4fd1c7a4a24c5cd4
```

## Recorded beta.4 results: GPU mining paused

**On one Threadripper PRO 7995WX, with GPU mining paused and all six fan channels
at the Mining100 profile**, the 192-worker hugetlb build recorded a
**121.157 kH/s mean displayed local rate**, with a **120.908 kH/s minimum**.
The compiler was GCC 15.2.0, using the ordinary non-PGO recipe. CPU clock and
voltage settings were unchanged for this test. These conditions are part of
the result; this is not a GPU-on or other-hardware 120 kH/s promise.

| Hour-run observation | Result |
| --- | ---: |
| Settling time before measurement | 600 seconds |
| Conservative active USER coverage after settling | 3,671.545 seconds |
| Counted displayed Local samples | 366 |
| Mean of the counted displayed rates | 121.157224 kH/s |
| Minimum counted displayed rate | 120.908 kH/s |
| Accepted USER shares during measurement | 393 |
| Rejected / unresolved work | 0 / 0 |

The mean is the **unweighted arithmetic mean of rounded Local display samples**.
It is not an independently measured raw-counter hour rate, a pool-side hashrate
estimate or a payout measurement. The counted samples span more than one hour;
no counted pause, reconnect or error was recorded, and the owned miner shut
down normally. A separate GPU-on attempt did not meet the strict displayed
120 kH/s minimum and is not presented as a pass.

Two shorter **real Kryptex pool runs on the same 7995WX**, still with GPU mining
paused and Mining100 cooling, tested lower worker counts on the same native
artifact. These are separate from the hour run:

| Desktop workers | Actual measured interval | Completed-hash local rate | Accepted USER shares in interval |
| ---: | ---: | ---: | ---: |
| 24 | 311.380 seconds | 23.844454 kH/s | 3 |
| 32 | 311.512 seconds | 31.786244 kH/s | 13 |

Those rates use completed-hash counter differences over the actual intervals,
after at least 60 seconds of settling. Both runs recorded zero rejected or
unresolved work. They do not establish one-hour results at those worker counts.

Three **other CPU rigs** separately rebuilt this source and passed full native
correctness, their actual huge-page worker checks and startup validation with
accepted Kryptex USER shares: 32 and 24 workers with GCC 13.3.0, and 24 workers
with GCC 11.4.0. Existing configuration and service policies were preserved,
with no GPU changes reported. These startup checks are portability evidence;
they are not the desktop measurements above or sustained speed claims.

See the [dated sanitized evidence](docs/evidence/beta4-validation-20261106.json)
for source/build identities, exact measurements and limits. No universal fastest
profile, matched 5% advantage over BzMiner, completed beta.4 fee cycle or deliberate
live reconnect-recovery test is claimed.

## What changed from beta.3

- Revised the selected XelisHashV3 kernel with exact arithmetic and index-fold
  optimizations, shared arithmetic tails and guarded square-root estimates.
  Full reference hash and scratchpad checks remain required.
- Added the selected folded-A salt expression and compiler barrier while
  preserving its arithmetic result. Performance remains compiler-dependent.
- Preserved the worker runtime, configuration format, reference verification,
  bounded nonce tracking and disclosed developer mining-time policy.

The canonical archive is unchanged. Its included README, CHANGELOG and
VALIDATION.json describe an **earlier development checkpoint**, including older
selected-kernel hashes and an earlier 118 kH/s acceptance plan. The dated
external report for current manifest `90ca3e0d…` and tested desktop native
`f5072ba1…` **supersedes those earlier validation descriptions**. Read the
[public addendum](https://github.com/FrogHollowFirewood/overxelis-miner/releases/download/v1.0.0-beta.4-public-preview.1/BETA4-PUBLIC-VALIDATION-NOTES.md)
for the full identities and current build instructions. The development-side
STAGING-METADATA mentioned internally is not shipped or needed to build.

## Build and run

Use Linux x86-64, an AES-NI-capable CPU, Python 3.10+ and GNU binutils. GCC 15.2
was used for the recorded desktop profile. Existing GCC 13.3 and 11.4 builds
also passed correctness and pool startup on the separate rigs described above;
every new compiler/CPU combination still needs its own qualification.

Stop any existing CPU miner normally before building or qualifying. Build as
a normal user on the mining computer: `-march=native` makes the output specific
to that host's instruction support. Do not copy the desktop native library to
another computer or add `-ffast-math`.

Download the archive and checksum into one directory, then stop on any failure:

```bash
sha256sum --check SHA256SUMS-beta.4-public-source-preview.1.txt &&
tar -xzf OverXelis-Miner-1.0.0-beta.4-public-source-preview.1.tar.gz &&
cd OverXelis-Miner-1.0.0-beta.4-public-source-preview.1
```

Use the actual absolute path of an existing trusted GCC executable. To follow
the recorded desktop compiler profile, select GCC 15.2:

```bash
python3 -I -B build_public.py --compiler /absolute/path/to/gcc15 &&
python3 -I -B qualify_public.py &&
bash run.sh --self-test
```

Full qualification replays 1,031 saved Rust hash answers through four C
implementations and compares complete reference scratchpads. It does not
rerun Rust or benchmark throughput. Preserve the resulting local build and
qualification records; build in a fresh verified directory when rebuilding.

For a new setup, create and review a private configuration before mining:

```bash
bash run.sh --configure &&
bash run.sh --check &&
bash run.sh --accept-dev-fee
```

Use `--config /absolute/path/to/private-config.json` with `--check` and mining
to read an existing configuration. The wizard refuses to overwrite an existing
file. Enter only a **public payout address**; no seed phrase or private key is
needed. The public examples contain invalid payout placeholders and cannot
start mining as supplied.

Press **Ctrl+C** to stop. Ordinary memory is available for initial setup.
`config.7995wx.example.json` requests 192 threads and hugetlb; use it only with
huge pages and permissions already configured. The program refuses silent
memory-mode fallback. The source preview installs no service, compiler or
system package and changes no global clock, power or huge-page settings.

Read the [included source guide](miner/README.md),
[packaging notes](miner/PUBLIC-PREVIEW-NOTES.md),
[security information](miner/SECURITY.md) and [release history](RELEASE-NOTES.md).
A checksum detects unexpected file changes; it is not a publisher signature.

## Preserved history and project scope

Beta.3 and beta.2 archives, tags and dated evidence remain available.
[Historical beta.3 validation](docs/evidence/beta3-validation-20261101.json)
recorded a 110.870 kH/s local session average during a 300-second pool run on
its own GCC14/192-worker desktop profile. Its earlier matched beta.2 comparison
belongs to that historical test. Hardware, memory, compiler and test conditions
changed for beta.4, so these figures do not establish a matched beta.4 speedup.
Beta.2's earlier fee transition and partial longer run remain
[beta.2 evidence](docs/evidence/preview2-early-ended-validation-20261029.json).

The website is in `docs/`; auditable source is in `miner/`. The website does not
mine in browsers, accept payments, collect configuration fields or install
software automatically. No Windows, macOS, ARM, GPU or automatic service package
is supplied. Run only on computers you own or are authorized to use.

OverXelis is not affiliated with or endorsed by XELIS or Kryptex. Project code
is MIT licensed; third-party components retain their included notices and licenses.
