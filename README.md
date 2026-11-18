# OverXelis v1.1.1

[Download v1.1.1 source](https://froghollowfirewood.github.io/overxelis-miner/downloads/OverXelis-Miner-1.1.1-source.tar.gz) · [SHA-256 checksum](https://froghollowfirewood.github.io/overxelis-miner/downloads/SHA256SUMS-v1.1.1.txt) · [Install guide](https://froghollowfirewood.github.io/overxelis-miner/guide.html) · [Release history](https://github.com/FrogHollowFirewood/overxelis-miner/releases)

OverXelis v1.1.1 is the final Linux x86-64 CPU miner for XELIS. Beta testing is complete. This release promotes the selected beta.5 kernel and pool runtime. Build and qualify on each mining host using Python 3.10+, GNU binutils, an AES-NI-capable CPU and a trusted GCC installation.

## Recorded performance

The four machines recorded **608.07 machine-hours** of Kryptex testing before promotion, through **18 November 2026 at 15:20 UTC**. Each ran one huge-page worker per configured thread. The two 24-thread rigs contributed **290.30 machine-hours** together.

| Machine | Threads | Total recorded hours | Average across sessions (kH/s) | Last session (hours) | Last session average (kH/s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Threadripper PRO 7995WX desktop | 192 | 170.87 | 122.698 | 70.34 | 123.115 |
| CPU Rig 1 | 32 | 146.91 | 12.469 | 94.01 | 12.462 |
| CPU Rig 2 | 24 | 143.67 | 8.561 | 94.01 | 8.558 |
| CPU Rig 3 | 24 | 146.63 | 9.152 | 94.01 | 9.152 |

The rates are gross local displays. The average across sessions weights each recorded session by its elapsed time. The last-session rate covers the session running at the cutoff. Total recorded runtime includes warmup and reconnects and excludes downtime between sessions and failed starts. Thread count alone does not determine speed.

Across 55 sessions, Kryptex accepted 85,130 user shares and 858 fee shares. The logs recorded 9 rejected shares and 195 unresolved submissions. Rig 2 had 1,336 additional starts without a recorded mining status. Package power was not measured and the 140 kH/s desktop target remains unverified.

[Recorded measurements and share counts](docs/evidence/v1.1.1-runtime.json) · [Beta.1–beta.5 history](RELEASE-NOTES.md)

Use ordinary pages for a first run unless your host already provides huge
pages. The miner checks the requested memory mode. Stop an existing CPU
miner normally before building, qualifying or starting another.

## Verify, build and qualify

Obtain the archive and matching checksum file from the release, and compare the
checksum with an independently displayed release digest when available.
Checksums detect file changes; they are not publisher signatures.

~~~sh
sha256sum --check SHA256SUMS-v1.1.1.txt &&
tar -xzf OverXelis-Miner-1.1.1-source.tar.gz &&
cd OverXelis-Miner-1.1.1
~~~

Stop if verification fails. Use an already installed, trusted GCC executable
or a previously verified private compiler wrapper. Replace the example below with your installed compiler path:

~~~sh
python3 -I -B build_public.py --compiler /usr/bin/gcc &&
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

For a hugetlb configuration, check the worker layout after kernel qualification.
Replace 192 with the number of configured threads on this host:

~~~sh
python3 -I -B tools/qualify_worker_layout.py --threads 192 \
  --output evidence/worker-layout-qualification.json
~~~

This offline check verifies one terminal nonce per worker against the C
reference and requires all requested workers to use hugetlb. It is a correctness
check, not a hashrate test or thread-count recommendation.

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
are skipped without debt or catch-up, and restarting resets the miner’s
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

## Troubleshooting and evidence

Keep the build and qualification receipts for your exact source, compiler,
library and host. Stop on verification failure or invalid share diagnostics.
Report reproducible issues with redacted logs and the CPU, compiler, thread
count, memory mode, elapsed time and share counts. Keep payout configuration,
credentials and raw logs private.
