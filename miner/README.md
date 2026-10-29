# OverXelis Miner 1.0.0-beta.2
## Public source preview 2 · Linux CPU mining for XELIS

**Experimental software for volunteer testers.** This is a build-from-source
preview, not a Windows executable, universal Linux binary, or stable release.
The native hashing sources and developer-fee schedule come from the tested
private beta.2 rig edition. The general-purpose setup wizard, launcher, and
packaging are new; live operation of this exact public package is not yet
verified. A complete live developer-fee cycle and long-term reliability remain
open validation items. No speed advantage or earnings level is guaranteed.

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

Linux x86-64, an AES-NI-capable CPU, Python 3.10+, GCC with GNU binutils, and
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

On Ubuntu/Debian, the prerequisites can be installed through the system's
package manager (administrator permission is needed only for that operation):

```bash
sudo apt update
sudo apt install python3 build-essential binutils
```

Review those commands and your operating system's package instructions first.
The miner does not execute them automatically. Stop any existing CPU miner
normally before building, qualifying, or running this preview.

## Download and verify

Obtain the archive and matching `SHA256SUMS-public-source-preview.2.txt` from the same release page.
Compare against the release's independently displayed SHA-256 when available.
A checksum detects unexpected file changes; it is **not a publisher signature**.

```bash
sha256sum --check SHA256SUMS-public-source-preview.2.txt &&
tar -xzf OverXelis-Miner-1.0.0-beta.2-public-source-preview.2.tar.gz &&
cd OverXelis-Miner-1.0.0-beta.2-public-source-preview.2
```

Do not proceed on a checksum failure. The tarball contains source and retained
public test vectors, not a precompiled binary or anyone's user configuration.

## Build and check the hash engine

```bash
python3 -I -B build_public.py &&
python3 -I -B qualify_public.py &&
bash run.sh --self-test
```

The build refuses unresolved native symbols and checks all required exports.
The qualifier checks 1,031 inputs through four C implementations, compares
full scratchpad contents, and replays saved answers from the independent Rust
reference. It does not newly execute Rust on your computer. Any failure blocks
mining. Preserve `build/` and `evidence/` logs rather than forcing past a failed
check. Existing output is not overwritten by a second build; extract a fresh
copy when rebuilding and retain the failed evidence separately.

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

The payout check is basic syntax validation, not a cryptographic address-checksum
or ownership proof. Double-check the address; the pool must accept it. There is
no default user payout address. The distributed example deliberately contains
an invalid placeholder so it cannot silently mine to the developer as USER.

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
- **Duplicate cache full:** the retained 32,768-entry protection stops this beta.
  Save the log and restart manually. This is a known long-session limit.
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

Private beta.2 builds have shown pool-accepted work with 192, 32, and 24 threads.
Those observations do not establish every CPU or distribution, the new public
launcher, prolonged operation, or a matched 5% advantage over BzMiner. Public
packaging changes are recorded in `PUBLIC-PREVIEW-NOTES.md`. This is for willing,
informed testers and machines they own or are authorized to use.

## License and sources

MIT-licensed project code and third-party notices are included. See `LICENSE`,
`THIRD_PARTY_NOTICES.md`, and the retained vendor license files. Portions of the
consensus hashing/cryptography originate from XELIS, BLAKE3, ChaCha20-SIMD and
TNN-derived work; the project does not claim those components as new inventions.
It is an independent project, not an official XELIS or Kryptex product.

References: [XELIS Stratum specification](https://docs.xelis.io/developers-api/stratum),
[Kryptex Xelis endpoints](https://pool.kryptex.com/xel/),
[XELIS reference source](https://github.com/xelis-project/xelis-hash).
