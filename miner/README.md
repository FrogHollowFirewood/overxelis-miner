# OverXelis Miner 1.0.0-beta.3
## Public source preview 1 · Linux CPU mining for XELIS

**OverXelis Miner beta.3 public source preview.** Experimental build-from-source
Linux CPU miner, prepared for validation and acceptance. No binary is included.
This archive preserves the chosen development candidate's native source and
build logic, and includes a precise benchmark child-cleanup correctness fix. Correctness, target performance, stable pool operation and a full
real developer-fee cycle remain acceptance checks. No target hashrate or matched
BzMiner advantage is claimed by this immutable source package.

Completed measurements and acceptance evidence belong in the separate development
kit report. See `DEVELOPMENT-NOTES.md` for the source boundary and test plan.

## What it does

OverXelis performs XelisHashV3 CPU work and connects to a compatible XELIS
Stratum pool. You supply your own **public payout address**, worker name, and
pool. You keep control of your wallet. No seed phrase, private key, exchange
login, deposit, browser miner, or account registration is needed by this program.

The source includes a disclosed **1% scheduled developer mining-time allocation**.
It starts with 5,940 seconds (99 minutes) of active user work, then allows a
fee window of up to 60 seconds, including connection setup. USER and FEE use
separate connections and worker names. The developer destination is:

- Pool: `stratum+tcp://xel-us.kryptex.network:7019`
- Public payout address: `xel:pqu4e39zln0g7lx9grdhj3tavuy6e45sjglp9ss9n6lx2zc0w9fqqxhxxvt`

The user's password is not reused for the developer login. Already-mined user
shares are not relabelled as developer shares. Paused/offline user time does
not count toward the next fee window. Failed fee connections are skipped,
without accumulated debt or catch-up. Restart resets this beta's schedule;
short sessions can contribute less than 1%. Scheduler timing is not hard
real-time and is logged. Share discovery is random, so **1% time does not mean
exactly 1% of coins**. Pool fees, network charges, energy costs, and brief
connection handovers are separate. The fee is not a wallet withdrawal.

## Requirements and scope

Linux x86-64, an AES-NI-capable CPU, Python 3.10+, GCC 14 with GNU binutils, and
an Internet connection to your chosen XELIS pool. Compilation uses
`-march=native`: build on the machine that will mine. Do not move that resulting
library to a CPU with different instruction support. No Windows, macOS, ARM,
GPU, or automatic service installation is supplied.

Run as a normal user. The public program refuses root. Use `ordinary` memory
for a first test; it needs no system huge-page configuration. `hugetlb` is an
optional explicit choice for users who already have Linux huge pages and
permissions configured. The program never changes CPU clocks, power limits,
GPU settings, firewall rules, system services, or kernel memory settings.
The published private-test rates used huge pages; ordinary-memory performance
may be different. A public non-root huge-page setup is not assumed to work.

Arrange Python 3.10+, GCC 14 and GNU binutils through a trusted operating-system
or private toolchain setup before building. This source package includes no
installer and fetches no compiler, package, executable or external code. Stop
any existing CPU miner normally before building, qualifying or running it.

## Download and verify

Obtain the archive and matching `SHA256SUMS-beta.3-public-source-preview.1.txt` from the same release page.
Compare against the release's independently displayed SHA-256 when available.
A checksum detects unexpected file changes; it is **not a publisher signature**.

```bash
sha256sum --check SHA256SUMS-beta.3-public-source-preview.1.txt &&
tar -xzf OverXelis-Miner-1.0.0-beta.3-public-source-preview.1.tar.gz &&
cd OverXelis-Miner-1.0.0-beta.3-public-source-preview.1
```

Do not proceed on a checksum failure. The tarball contains source and retained
public test vectors, not a precompiled binary or anyone's user configuration.

## Build and check the hash engine

Use an already installed **GCC 14** executable or the approved private GCC14
wrapper. Replace `/absolute/path/to/gcc14` below with its actual absolute path.
These instructions use the ordinary **non-PGO** build. GCC 11 is not the
recommended compiler for this preview: its historical development build was
slower on the target. Compiler selection is explicit; no automatic detection,
installation, global compiler change or LD environment change is supplied.

```bash
python3 -I -B build_public.py --compiler /absolute/path/to/gcc14 &&
python3 -I -B qualify_public.py &&
bash run.sh --self-test
```

Compilation retains the selected candidate's exact flags and strict native
export/link checks. Full qualification checks 1,031 saved Rust answers through
four C implementations and compares entire scratchpads. It replays saved answers,
not fresh Rust execution. Preserve build/evidence logs and stop on any failure.
The optional PGO recipe remains experimental; it is not the recommended build
or a substitute for full qualification and independent unseen-work checks.

## Check the actual hugetlb worker layout

After full kernel qualification passes, users with huge pages already available
can check every worker scratchpad before benchmarking:

```bash
python3 -I -B tools/qualify_worker_layout.py --threads 192 \
  --output evidence/worker-layout-192.json
```

This offline correctness check gives each worker exactly one terminal nonce,
checks all returned hashes against the C reference, and requires every worker
to use hugetlb memory. It makes no pool connection. A 192-worker correctness
check does not select the fastest mining thread count.

The 7995WX has 192 logical threads. Match the exact thread count, CPU order,
memory mode, compiler, power and thermal conditions when comparing builds.
The optional 192-thread profile is an explicit setting, not a universal fastest
placement. Consult the separate development-kit report for completed measurements.

## Add your wallet, pool, and worker

The wizard writes a private local configuration file, but does not start mining:

```bash
bash run.sh --configure
```

Enter your mainnet `xel:` payout address. This is **not** your seed phrase. Enter
a compatible pool URL, such as Kryptex's North America TCP endpoint:

```text
stratum+tcp://xel-us.kryptex.network:7019
```

The endpoint is a suggested default, not a requirement. Only the fee destination
is fixed by this preview. Other pool compatibility is not guaranteed. Supported
URL forms are `stratum+tcp://host:port`, `stratum+ssl://host:port`, and
`stratum+tls://host:port`; use the port published by the pool. TLS connections
verify the certificate and hostname. TCP traffic is unencrypted. Do not place
passwords inside a pool URL or use your exchange-account password as a worker
password. The usual pool worker password is `x`, unless the pool specifies another.

Choose a unique worker label, a thread count your computer supports, and
`ordinary` or `hugetlb`. The wizard's default thread count uses discovered
physical cores first; you may choose a different number. Too many threads can
make the computer unresponsive and does not guarantee more hashrate.

Review the file and check it without hashing or connecting:

```bash
bash run.sh --check
```

### Optional explicit CPU order

Omit `cpus`, or set it to `null`, to keep the existing automatic physical-first
selection. For a measured placement, add a JSON array named `cpus` containing
one CPU identifier per thread, in the exact worker order you want. Its length
must equal `threads`; every identifier must be a distinct integer in the current
process affinity. Booleans, strings and repeated or unavailable CPUs are rejected
before hashing or networking starts. `--check` prints the selected `cpus` order
for review. The configuration wizard keeps its existing automatic behavior.

The read-only proposal tool is specific to the target's 192 logical CPUs,
96 two-way SMT cores, 12 LLC groups and four NUMA nodes:

```bash
python3 -I -B tools/balanced_threads.py --threads 160 176 192 --rotation 0
```

It preserves the original physical-core pass, then spreads extra SMT workers
across NUMA nodes and LLC groups. Unsupported topology fails closed. It only
prints proposals; it starts no native workers, makes no network connection and
writes no configuration. Copy a proposal's `threads` and `ordered_cpus` values
into your configuration's `threads` and `cpus` fields, then run `--check`.
Rotations 0 through 7 change which physical cores receive added SMT workers.
A proposal is not a benchmark result or a claim that it is the fastest choice.
The older benchmark `--cpus` string parser still sorts CPU lists; an ordered JSON
array is required when worker order matters.

The payout check is basic syntax validation, not a cryptographic address-checksum
or ownership proof. Double-check the address; the pool must accept it. There is
no default user payout address. The distributed example deliberately contains
an invalid placeholder so it cannot silently mine to the developer as USER.

## Optional 7995WX profile

`config.example.json` keeps the original ordinary-memory settings. The separate
`config.7995wx.example.json` explicitly requests 192 threads, `hugetlb`, and
`cpus: null` for automatic physical-first order. Both examples contain an invalid
public wallet placeholder and cannot start mining as distributed. Copy the desired
example to a private `config.json`, enter your own public payout address, pool and
worker, and review it with `bash run.sh --check` before starting. The profile is
optional, assumes already configured huge pages, and does not select a universal
fastest thread count or change operating-system settings.

## Start and stop

```bash
bash run.sh --config config.json --accept-dev-fee
```

Keep the terminal open. Press **Ctrl+C** to stop. To run a finite initial test:

```bash
bash run.sh --config config.json --accept-dev-fee --duration 900
```

A short test does not validate the fee transition. The first fee window follows
99 **active** user-mining minutes. Keep a session running through an observed
`DEV FEE START` → `DEV FEE END` → resumed USER work before claiming fee-cycle
success. A fee window can find no share by chance; that alone is not failure.

Look for authorization, accepted USER shares, the intended worker count, and
no invalid-local results. The console separates USER and FEE shares, reports
local completed-hash rate, and logs elapsed active time. Its local/session
rate includes both roles and is **gross throughput**, not net user payout.
Pool-side rates depend on accepted shares and may vary in short samples.

## Troubleshooting

- **Missing files / checksum mismatch:** stop and obtain a fresh matching release.
  Do not bypass the integrity check or mix source editions.
- **Build or hash qualification fails:** preserve logs, compiler version and CPU
  model. Do not mine with the failed binary.
- **Another miner detected:** stop that CPU miner using its own normal procedure.
  OverXelis never kills it or disables its service.
- **Huge pages unavailable:** use `ordinary` for the initial test, or configure
  huge pages yourself using trusted instructions. The program refuses silent
  fallback when `hugetlb` was requested.
- **Authorization fails:** check your public address, pool, worker and worker
  password. This is not a reason to send a private key to anyone.
- **Paused connection:** this source preview reconnects after 30 continuously
  paused seconds without usable work. An active miner is not reconnected solely
  because no share was found.
- **Low rate:** record a sustained sample after warmup. Compare equal thread,
  memory, power, thermal and workload settings. Startup peaks are not a benchmark.
- **Long sessions:** production tracks the highest submitted nonce in each native
  worker stream. Its storage stays bounded by the worker count, while repeated
  or lower nonces remain suppressed through reconnects and USER/FEE changes.
  The legacy exact-input limit remains for injected test engines without native
  stream guarantees. A nonce session must never be reset on an existing engine.
- **Security software warning:** do not disable protections blindly. Review the
  source, checksum, release identity and the warning before deciding to proceed.

## Feedback

Use the project's GitHub issue forms for bugs or benchmark results. Provide the
version **and packaging edition**, Linux distribution, CPU model, compiler,
threads, memory mode, duration, local average, accepted/rejected counts, reconnects,
and a short redacted log. State whether a full fee cycle completed. For a speed
comparison, name the other miner/version and match settings. Do not post seed
phrases, private keys, passwords, API tokens, IP addresses, full payout addresses,
or unredacted configuration files. Public issues are visible to everyone.

## Evidence and limitations

This immutable package describes source and validation requirements. Completed
hash qualification, target performance, pool operation and real fee-cycle evidence
belong in the separate development-kit report. Results for an earlier development
tree do not establish acceptance of a newly built public artifact. Provide the
exact edition, compiler, build identity and settings when reporting a result.

## License and sources

MIT-licensed project code and third-party notices are included. See `LICENSE`,
`THIRD_PARTY_NOTICES.md`, and the retained vendor license files. Portions of the
consensus hashing/cryptography originate from XELIS, BLAKE3, ChaCha20-SIMD and
TNN-derived work; the project does not claim those components as new inventions.
It is an independent project, not an official XELIS or Kryptex product.

References: [XELIS Stratum specification](https://docs.xelis.io/developers-api/stratum),
[Kryptex Xelis endpoints](https://pool.kryptex.com/xel/),
[XELIS reference source](https://github.com/xelis-project/xelis-hash).
