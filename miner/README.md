# OverXelis Miner 1.0.0-beta.4
## Public source preview 2 · Linux XelisHashV3 CPU miner

This edition builds the miner from source on the mining computer. It includes
the selected XelisHashV3 CPU kernel, a foreground Stratum client, a disclosed
1% developer mining-time policy, and offline correctness checks. No native
binary or private user configuration is distributed.

This edition adds protection for the recorded beta.4 integer division-by-zero
fault. The selected production kernel checks the round result before modular
power. If that modulus is zero, the runtime consumes and skips the nonce,
records a separate diagnostic, and continues. A failed attempt is never counted
as a completed hash or submitted as a share; no substitute digest is invented.

The historical failing input was not retained. The reason its round result
became zero remains unverified. This patch protects the observed failure path;
it does not establish that every possible native failure is eliminated.
Reference and experimental kernels retain their original zero-modulus behavior.
The legacy void selected-kernel API deliberately traps on an error; production
mining uses its checked API.

Two development-hotfix GPU-on tests on a Threadripper PRO 7995WX at 192 threads
measured 119.303 and 118.955 kH/s over approximately 191 seconds after settling,
with 25 and 28 accepted USER shares during those measured windows and zero
rejected or unresolved shares. These are short local-rate observations, not a
one-hour qualification or a performance guarantee. The older 121.157 kH/s
GPU-paused hour used the unpatched build and is historical evidence only.
Use the release validation addendum to match these results to the exact source
package and resulting native library.

## Requirements

Use Linux x86-64, an AES-NI-capable CPU, Python 3.10 or newer at
`/usr/bin/python3`, GCC 15 and GNU binutils. The documented build is non-PGO and uses `-march=native`; compile
on the computer that will mine. The resulting library can require that CPU's
instruction set. The selected arithmetic requires strict binary64 behavior;
do not add `-ffast-math`.

Run as a normal user; the program refuses root. Stop an existing CPU miner
normally before building, qualifying or running this one. The source package
installs no compiler, service or system package and changes no global compiler,
clock, power-limit, huge-page or operating-system setting.

Use `ordinary` memory for an initial setup without huge pages. Choose `hugetlb`
only when the host already provides the required huge pages and permissions;
the miner refuses silent fallback. The target 192-worker profile assumes this
host setup and does not establish the fastest setting for another machine.

## Verify, build and qualify

Obtain the archive and matching checksum file from the release, and compare the
checksum with an independently displayed release digest when available.
Checksums detect file changes; they are not publisher signatures.

~~~sh
sha256sum --check SHA256SUMS-beta.4-public-source-preview.2.txt &&
tar -xzf OverXelis-Miner-1.0.0-beta.4-public-source-preview.2.tar.gz &&
cd OverXelis-Miner-1.0.0-beta.4-public-source-preview.2
~~~

Stop if verification fails. Use an already installed, trusted GCC 15 executable
or a previously verified compiler wrapper. Replace the example below with the
actual absolute path of that trusted executable:

~~~sh
python3 -I -B build_public.py --compiler /absolute/path/to/gcc15 &&
python3 -I -B qualify_public.py &&
bash run.sh --self-test
~~~

The compiler and any wrapper live outside the miner source tree. Passing
`--compiler` does not change the global compiler or require a global PATH or
library-path override. The source archive does not download or install that
toolchain. A different compiler or host needs its own qualification and rate
measurements.

Run these commands in order and stop on any failure. Full qualification replays
1,031 saved Rust hash answers through four C implementations and compares entire
scratchpads. It does not rerun Rust. The self-test makes no pool connection.
Keep `build/build.json` and `evidence/kernel-qualification.json`. Existing
build output is not overwritten; rebuild in a fresh verified source directory
to preserve the previous build and evidence.

On the target host, check the actual 192-worker hugetlb layout after kernel
qualification:

~~~sh
python3 -I -B tools/qualify_worker_layout.py --threads 192 \
  --output evidence/worker-layout-qualification.json
~~~

This offline check verifies one terminal nonce per worker against the C
reference and requires all requested workers to use hugetlb. It is a correctness
check, not a hashrate test or thread-count recommendation.

For a thread profile you intend to use, retain its own actual-worker checks and
rate measurements. A 24- or 32-worker result does not qualify 192-worker
throughput. Forced-failure tests at 1, 24, 32 and 192 workers validate error
handling; they are not hashrate measurements.

## Configure and check

After normal build and kernel qualification, reproduce the zero-modulus guard
using a separate test library. This is a correctness check and uses no pool or
private configuration. Production sources and the mining library remain unchanged:

~~~sh
python3 -I -B tools/test_zero_modulus.py --compiler /absolute/path/to/gcc15 \
  --threads 1 24 32 192 --page-mode ordinary
~~~

On a host with huge pages already configured, use `--page-mode hugetlb` to
exercise those actual worker allocations. The test writes its own generated
library and report into a fresh `evidence/zero-modulus-*` directory. Never use
that deliberately failing test library for mining.

Keep an existing pool/worker configuration in its current private location and
pass it explicitly. The check and mining commands read that file; they do not
rewrite its settings.

~~~sh
bash run.sh --config /absolute/path/to/private-config.json --check
~~~

To create a new configuration interactively, choose a new file path:

~~~sh
bash run.sh --config /absolute/path/to/new-private-config.json --configure
~~~

The wizard writes a private file and starts no mining. It refuses to overwrite
an existing file. Enter a public mainnet payout address, compatible pool URL,
worker name, pool worker password, thread count and memory mode. No private key
or seed phrase is required. Address checks validate shape, not ownership or a
cryptographic address checksum; verify your public address independently.

The supplied examples contain invalid payout placeholders. The optional 7995WX
example requests 192 threads, hugetlb and automatic physical-first CPU order.
An optional `cpus` JSON array selects an explicit worker order; it must contain
one distinct, available integer CPU identifier per thread. Always run
`--check` after preparing or changing a configuration. TLS pool URLs use
`stratum+ssl://` or `stratum+tls://` and verify the hostname and certificate;
`stratum+tcp://` traffic is unencrypted.

## Developer time policy

Mining requires explicit `--accept-dev-fee` acknowledgement. The disclosed 1%
schedule runs 5,940 seconds of active USER work, then a FEE window of up to
60 seconds including connection setup, before returning to USER work. USER
and FEE use separate connections and worker names. Fee destinations remain
visible in `overxelis_fee.py` and the run log.

Paused/offline USER time does not advance the schedule. Failed fee connections
are skipped without debt or catch-up, and restarting resets this beta's
schedule. The user's worker password is not reused for the developer login.
Share discovery is random: 1% scheduled time does not mean exactly 1% of coins.
Pool fees, energy costs and connection handovers are separate.

## Run and stop

~~~sh
bash run.sh --config /absolute/path/to/private-config.json --accept-dev-fee
~~~

Keep the terminal open and press Ctrl+C to stop. For a finite initial test,
append `--duration 900`; omitting it or using `--duration 0` runs until stopped.
The accepted finite duration range is 1–86,400 seconds.

Check the expected worker count, pool authorization, accepted USER shares,
rejections and reconnects. Local/session rates count completed hashes for both
roles and represent gross throughput. Pool rates depend on accepted shares and
can vary substantially over short samples.

A one-hour session does not by itself exercise the scheduled fee transition.
That requires at least 99 active USER minutes followed by an observed
`DEV FEE START`, `DEV FEE END` and resumed USER work. Record what actually
occurred; do not infer fee-cycle success from elapsed wall time alone.

## Evidence and troubleshooting

For the exact release source and compiled library, retain:

| Record | Purpose |
| --- | --- |
| `evidence/kernel-qualification.json` | Saved-answer, four-C and full-scratchpad results |
| `evidence/worker-layout-qualification.json` | Actual 192-worker hugetlb layout results |
| `evidence/worker-layout-24.json` and `worker-layout-32.json` | Count-specific actual hugetlb worker checks |
| `low-thread-rates.json` in the chosen measurement directory | Exact-build 24/32-worker counter rates |
| `evidence/sustained-screen/analysis.json` | Sustained, matched comparison and its settings, when produced |
| `evidence/hour-test/report.json` and `rates.csv` | Duration, pool counters and rate samples, when produced |

The latter records are acceptance evidence to be produced for the final
artifact; their names here do not assert that a screen or hour test passed.
Match the source manifest, library digest, compiler, CPU order, thread count,
memory mode and conditions before transferring a result to another build.
Earlier beta.3 or development-candidate results do not qualify this edition.

`VALIDATION.json` is a static description of this hotfix, per-build requirements
and evidence locations. It is not a completed test report. Each local build must
pass its native self-test and saved-answer qualification before mining. Retain
actual worker-layout and live-pool reports for the settings you use. Longer live
soak testing, a full scheduled fee transition, and matched performance
comparisons remain separate checks; no fixed-build hour result is asserted here.

A zero-modulus diagnostic is an error record, not an accepted share or completed
hash. The native `nx_skipped` counter and `nx_bad_input` capture API distinguish
these attempts from ordinary work. Preserve a captured failing input and report
it with the exact source/library identities for isolated reference replay.
Do not change the modulus, suppress correctness failures, or substitute a digest.

If build or hash checks fail, preserve the logs and stop. If hugetlb is
unavailable, use ordinary memory for setup or arrange host permissions outside
this program. For low rates, compare sustained samples after warmup with equal
settings. If pool authorization fails, check the public payout address, pool
and worker settings.

Report the version and edition, CPU, compiler, threads, memory mode, duration
and redacted results. Do not publish private configuration contents, passwords,
private keys or seed phrases.

## License and attribution

Project code is MIT-licensed; see `LICENSE` and `THIRD_PARTY_NOTICES.md`.
The hashing implementation derives from the XELIS MIT reference. TNN-derived
ChaCha and division work, ChaCha20-SIMD, and BLAKE3 retain their notices and
license files. These integrations are not a new consensus algorithm.
OverXelis is an independent project.

