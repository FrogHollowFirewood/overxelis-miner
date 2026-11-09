# OverXelis Miner

Independent XELIS CPU-mining software. **1.0.0-beta.4 / public-source-preview.2 — checked crash fix**

Experimental Linux x86-64 source preview. Build and qualify it on the computer
that will mine. Configure your own public payout address, pool, worker, thread
count, CPU order and memory mode. The disclosed **1% scheduled developer
mining-time allocation** remains 99 active USER minutes followed by a fee window
of up to 60 seconds.

## Upgrade from beta.4 preview 1

**The earlier beta.4 preview 1 is superseded because of a recorded integer
divide-by-zero crash**, displayed by the shell as “floating point exception.”
Use preview 2 in a fresh directory and rebuild and qualify it locally. Existing
release tags, archives, checksums and historical test records remain unchanged.

The selected production kernel now checks the zero-modulus state before division.
A failed nonce is consumed, is not counted as a completed hash, and cannot enter
the share queue. The first failing input is retained in native runtime memory for diagnostics; the public launcher does not automatically save it to disk.
No replacement modulus or invented hash is submitted. The historical failing
input was not saved, so the origin of its zero intermediate value remains
unverified. This repair addresses the observed selected-kernel failure; it does
not establish that every possible crash is prevented.

## Current beta.4 source download

- **[Download the beta.4 hotfix source archive](https://github.com/FrogHollowFirewood/overxelis-miner/releases/download/v1.0.0-beta.4-public-preview.2/OverXelis-Miner-1.0.0-beta.4-public-source-preview.2.tar.gz)**
- [Matching SHA-256 checksum](https://github.com/FrogHollowFirewood/overxelis-miner/releases/download/v1.0.0-beta.4-public-preview.2/SHA256SUMS-beta.4-public-source-preview.2.txt)
- [Hotfix validation notes](https://github.com/FrogHollowFirewood/overxelis-miner/releases/download/v1.0.0-beta.4-public-preview.2/BETA4-HOTFIX-VALIDATION-NOTES.md)
- [Preview-2 release page](https://github.com/FrogHollowFirewood/overxelis-miner/releases/tag/v1.0.0-beta.4-public-preview.2) · [All releases](https://github.com/FrogHollowFirewood/overxelis-miner/releases)
- [Website guide](https://froghollowfirewood.github.io/overxelis-miner/guide.html) · [Current hotfix report](https://froghollowfirewood.github.io/overxelis-miner/site-status.html#beta4-validation)

Use the named **source-only prerelease** and its matching checksum, rather than
GitHub's automatic repository ZIP. The archive is **314326 bytes**.
It contains public source, saved reference inputs and their manifest. No compiled
workstation library, live user configuration, private deployment kit or raw mining
logs are included.

```text
SHA-256: 4ede37b957b5024611f63714f4593bd60a849c0dd9c14594490353c56bdb53da
```

## Beta.5 development update · 9 November 2026

In a trial that ended November 9, 2026, a beta.5 development build ran on Kryptex for 33 hours, 31 minutes, 18 seconds on an AMD Threadripper PRO 7995WX with 192 huge-page workers. The miner displayed a session average of 124.060 kH/s. The run recorded 13,911 accepted user shares, 137 accepted fee shares, zero rejected shares and 13 unresolved submissions during connection interruptions. The CPU peaked at 83.875 °C, below the 85 °C guard. All workers closed normally after a requested stop.

The rate comes from the miner’s session display. The run did not capture a completed-hash counter window or CPU package power. It does not establish a matched speed gain or qualify the 140 kH/s target.

A separate Stage 3 patch passed offline checks against 1,031 saved Rust hash answers and full scratchpad comparisons. Single-worker forced-zero checks passed in both rounds. Desktop qualification and a matched Kryptex test are pending. **Beta.4 source preview 2 remains the public download.** See the [website development update](https://froghollowfirewood.github.io/overxelis-miner/#beta5-development).

## Added 6 November 2026: development-hotfix logged hour

After warmup, a completed 192-huge-page-worker Kryptex run recorded **60 minutes
27.49 seconds**, **119.739756 kH/s mean of 361 rounded local displays**, and a
sampled minimum of **119.517 kH/s**. The interval accepted **444 USER shares**;
the session accepted 450, with zero rejected or unresolved displayed, and native
workers closed normally after a requested stop.

The development native library matches the qualified preview-2 library byte for
byte; its launcher retained the earlier preview-1 banner. This is logged
continuity evidence, **not an exact raw-counter hour or an exact-edition launcher
run**. GPU activity, cooling, temperatures and native drop/undefined-skip counters
were not recorded. See the [dated report](docs/reports/beta4-hotfix-hour-20261106.md)
and [sanitized interval data](docs/evidence/beta4-hotfix-hour-continuity-20261106.json)
for build provenance, calculation and limits. The original source archive,
checksums and preparation-time validation remain unchanged.

## Measured hotfix results: short GPU-on tests

On one AMD Threadripper PRO 7995WX, **192 hugetlb workers, GCC 15.2, ordinary
non-PGO build and GPU mining running**, the qualified development hotfix recorded:

| Run | Actual measured interval | Completed-hash local rate | Accepted USER shares in interval |
| --- | ---: | ---: | ---: |
| First hotfix run | 191.063907 seconds | 119.302920 kH/s | 25 |
| Repeat hotfix run | 190.778115 seconds | 118.955001 kH/s | 28 |

Each interval follows at least 60 seconds of settling. Both measurements reported
zero rejected, unresolved or queue-dropped work. Rates use completed-hash counter
differences over the actual interval; they are not pool-side estimates or net
payout measurements. These are **two short observations**, not one continuous
combined window, an hour-long hotfix pass, a 24-hour soak or a universal speed promise.

The development hotfix passed 1,031 saved Rust-answer inputs through four C
implementations, full scratchpad comparisons and verification of 192 actual
huge-page workers. Forced-zero tests exercised 1, 24, 32 and 192 workers. Saved
Rust answers were replayed; fresh Rust was not executed. Exact-package build and
qualification identities are reported in the [hotfix evidence](docs/evidence/beta4-hotfix-validation-20261106.json)
and linked validation notes, rather than inferred from the version name.

The checked path protects the selected production kernel. Reference and
experimental kernels retain their earlier zero-modulus behavior, and the legacy
void selected API deliberately traps on failure. A captured failing input and
independent reference replay are still needed to determine whether the original
zero arose from a reference edge case, an optimization discrepancy or a transient
computation fault. No full hotfix fee cycle, deliberate live reconnect recovery,
matched BzMiner advantage or broad compiler/hardware qualification is claimed.

## Build and run

Use Linux x86-64, an AES-NI-capable CPU, Python 3.10+, GNU binutils and an installed,
trusted **GCC 15** executable. The recorded development hotfix used GCC 15.2.
Older GCC 13.3/11.4 rig checks belong to the unpatched source and do not qualify
this hotfix. Every new compiler/CPU combination needs its own qualification.

Stop any existing CPU miner normally before building or qualifying. Build as a
normal user on the mining computer: `-march=native` makes the library specific to
that CPU. Do not transfer it to different instruction support or add fast-math.

Download the named archive and matching checksum into one directory:

```bash
sha256sum --check SHA256SUMS-beta.4-public-source-preview.2.txt &&
tar -xzf OverXelis-Miner-1.0.0-beta.4-public-source-preview.2.tar.gz &&
cd OverXelis-Miner-1.0.0-beta.4-public-source-preview.2
```

Replace the compiler placeholder with the actual trusted installed GCC 15 path:

```bash
python3 -I -B build_public.py --compiler /absolute/path/to/gcc15 &&
python3 -I -B qualify_public.py &&
bash run.sh --self-test
```

Stop on any failure. Full qualification replays 1,031 saved Rust answers through
four C implementations and compares entire reference scratchpads. Preserve local
build and qualification records and use a fresh verified directory when rebuilding.

For a new setup, create and review a private configuration before mining:

```bash
bash run.sh --configure &&
bash run.sh --check &&
bash run.sh --accept-dev-fee
```

Use `--config /absolute/path/to/private-config.json` with `--check` and mining to
read an existing configuration. The wizard refuses to overwrite an existing file.
Use only your **public payout address**; no seed phrase or private key is needed.
The examples contain invalid payout placeholders and cannot mine as supplied.

Press **Ctrl+C** in the miner's own terminal to stop. Closing a separate log-viewer
window does not stop a background test controller. A shared-lock refusal means
another mining or test process may own the CPU session; stop it through its own
controller rather than deleting a live lock or launching a second CPU miner.

Ordinary memory is available for initial setup. `config.7995wx.example.json`
requests 192 threads and hugetlb; use it only with huge pages and permissions
already configured. Requested hugetlb does not silently fall back. This preview
installs no service, compiler or system package and changes no global clock,
power, fan or huge-page settings.

Read the [source guide](miner/README.md), [packaging notes](miner/PUBLIC-PREVIEW-NOTES.md),
[security information](miner/SECURITY.md) and [release history](RELEASE-NOTES.md).
A checksum detects unexpected file changes; it is not a publisher signature.

## Preserved history and project scope

Beta.4 preview 1, beta.3 and beta.2 archives, tags and dated evidence remain available.
The unpatched beta.4 GPU-paused hour averaged 121.157224 kH/s across 366 rounded
Local displays, minimum 120.908 kH/s, with 393 accepted USER shares. Its 24/32-thread
measurements and three physical-rig startup checks also belong to that earlier
source. Those records are historical evidence, not hotfix hour-long or rig
qualification. Preview 1 is superseded because of its known crash. See the
[preserved original beta.4 evidence](docs/evidence/beta4-validation-20261106.json).
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
