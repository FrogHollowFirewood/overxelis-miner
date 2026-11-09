# OverXelis Miner 1.0.0-beta.5

Experimental Linux x86-64 CPU miner for XELIS. Public source preview 1
contains the selected kernel and pool runtime used in the beta.5 development
trial, with public version metadata. Build and qualify it locally as a normal
user. Use an AES-NI-capable CPU, Python 3.10+, GNU binutils and a trusted GCC
15 compiler. Build with strict math and preserve the normal non-PGO settings.
The native library is compiled for the build host.

The Kryptex trial lasted 33 hours, 31 minutes, 18 seconds on one AMD
Threadripper PRO 7995WX with 192 huge-page workers. The miner displayed a
124.060 kH/s session average. Kryptex accepted 13,911 user and 137 fee shares.
The run recorded zero rejected shares and 13 unresolved submissions. The CPU
peaked at 83.875 °C under the separate desktop trial launcher's 85 °C guard.
The public CLI does not include that desktop-specific temperature monitor.
See the release notes for the limits of this trial and local build evidence.

Use ordinary pages for a first run unless your host already provides huge
pages. The miner checks the requested memory mode. Stop an existing CPU
miner normally before building, qualifying or starting another.

## Verify, build and qualify

Obtain the archive and matching checksum file from the release, and compare the
checksum with an independently displayed release digest when available.
Checksums detect file changes; they are not publisher signatures.

~~~sh
sha256sum --check SHA256SUMS-beta.5-public-source-preview.1.txt &&
tar -xzf OverXelis-Miner-1.0.0-beta.5-public-source-preview.1.tar.gz &&
cd OverXelis-Miner-1.0.0-beta.5-public-source-preview.1
~~~

Stop if verification fails. Use an already installed, trusted GCC 15 executable
or a previously verified private compiler wrapper. Replace the example below with your installed compiler path:

~~~sh
python3 -I -B build_public.py --compiler /absolute/path/to/gcc15 &&
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

## Troubleshooting and evidence

Keep the build and qualification receipts for your exact source, compiler,
library and host. Stop on verification failure or invalid share diagnostics.
Report reproducible issues with redacted logs and the CPU, compiler, thread
count, memory mode, elapsed time and share counts. Keep payout configuration,
credentials and raw logs private.

The trial rate is a session display value. CPU package power and a matched
speed comparison were outside the measured scope. The 140 kH/s target
remains open. The separate Stage 3 split-store experiment is outside this
source preview.
