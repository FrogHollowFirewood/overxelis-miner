# OverXelis Miner 1.0.0-beta.4
## Public source preview 1 · Linux XelisHashV3 CPU miner

This edition builds the miner from source on the mining computer. It includes
the selected XelisHashV3 CPU kernel, a foreground Stratum client, a disclosed
1% developer mining-time policy, and offline correctness checks. No native
binary or private user configuration is distributed.

The selected kernel expresses two C2 products through a readonly memory
operand and adds compiler probability annotations to existing square-root
guards. The low64 products, guard values and correction results stay exact.
The annotation probability is a compiler model, not a measured distribution.

The development target is a Threadripper PRO 7995WX with 192 workers and
already configured hugetlb memory. Performance depends on the exact compiler,
CPU placement, memory, power and thermal conditions. This document makes no
118 kH/s or completed one-hour acceptance claim. Use the matching evidence
records described below to assess the exact final build.

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
sha256sum --check SHA256SUMS-beta.4-public-source-preview.1.txt &&
tar -xzf OverXelis-Miner-1.0.0-beta.4-public-source-preview.1.tar.gz &&
cd OverXelis-Miner-1.0.0-beta.4-public-source-preview.1
~~~

Stop if verification fails. Use an already installed, trusted GCC 15 executable
or a previously verified private compiler wrapper. The target recipe passes the
private wrapper by its absolute path; replace this example with its actual path:

~~~sh
python3 -I -B build_public.py --compiler /absolute/path/to/toolchains/gcc15-jammy-b/gcc15 &&
python3 -I -B qualify_public.py &&
bash run.sh --self-test
~~~

The wrapper and toolchain live outside the miner source tree. Passing
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

Final acceptance also requires separate actual-worker checks at 24 and 32
workers, followed by 300 measured seconds at each count after 30 seconds of
warmup. Their results describe those profiles and do not replace the 192-worker
throughput gate.

## Configure and check

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

`VALIDATION.json` is a static description of the required checks and evidence
locations, not a test result. Acceptance requires the exact final 192-worker
build to sustain at least 118 kH/s in the independent completed-hash benchmark
and a live-pool window of at least 3,660 seconds after settling. The reviewed
external soak runner supports `--measure-seconds 3660 --settle-seconds 120
--max-runtime-seconds 7200`; its default one-hour duration is shorter than this
release requirement. Retain its duration proof and displayed rate samples;
rounded display samples do not replace the independent throughput gate.

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

