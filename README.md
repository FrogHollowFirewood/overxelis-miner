# OverXelis Miner

Independent XELIS CPU-mining software. **1.0.0-beta.3 / public-source-preview.1**

Experimental Linux x86-64 source preview for volunteer testers, with configurable
public payout address, pool, worker, thread count, CPU order and memory mode.
The disclosed **1% scheduled developer mining-time allocation** is unchanged:
99 active USER minutes followed by a fee window of up to 60 seconds.

## Releases / Latest beta.3 download

- **[Download beta.3 source archive](https://github.com/FrogHollowFirewood/overxelis-miner/releases/download/v1.0.0-beta.3-public-preview.1/OverXelis-Miner-1.0.0-beta.3-public-source-preview.1.tar.gz)**
- [Download its SHA-256 checksum](https://github.com/FrogHollowFirewood/overxelis-miner/releases/download/v1.0.0-beta.3-public-preview.1/SHA256SUMS-beta.3-public-source-preview.1.txt)
- [Beta.3 release page and notes](https://github.com/FrogHollowFirewood/overxelis-miner/releases/tag/v1.0.0-beta.3-public-preview.1) · [All releases](https://github.com/FrogHollowFirewood/overxelis-miner/releases)
- [Website guide](https://froghollowfirewood.github.io/overxelis-miner/guide.html) · [Current validation status](https://froghollowfirewood.github.io/overxelis-miner/site-status.html#beta3-validation)

This is a **source-only prerelease**. Use the named archive and matching checksum,
not GitHub's automatic repository ZIP. No precompiled workstation binary or private
user configuration is included. Source archive SHA-256:

```text
a53075dd73977796281780767ff4387c8c788a951630a468b5591fd6731cee12
```

The archive's internal README and VALIDATION.json preserve its preparation-time
boundary. The subsequent exact-package build, correctness and live-pool results
are documented in the [dated sanitized evidence](docs/evidence/beta3-validation-20261101.json)
and [current website report](https://froghollowfirewood.github.io/overxelis-miner/site-status.html#beta3-validation).
The verified archive has not been regenerated to insert later results.

## Recorded beta.3 results

One AMD Threadripper PRO 7995WX desktop was tested with **192 threads, hugetlb
memory and GCC 14.3.0**, normal non-PGO builds, with other CPU mining stopped.
Both benchmark comparators used the same compiler, thread count, ordered CPU
selection and memory mode.

| Measurement | Local rate | Test context |
| --- | ---: | --- |
| Beta.2 public-source-preview.2 | 110.234 kH/s | Four separate 60-second benchmark samples |
| Beta.3 selected native build | **111.168 kH/s** | Four separate 60-second samples; **+0.85%** time-weighted throughput |
| Exact public beta.3 package, live pool run | **110.870 kH/s** | Local session average over a 300-second run; **38 accepted shares, zero rejects** |

The benchmark used four alternating-order pairs, a fresh process per sample and
15 seconds of warmup per sample. Its candidate rates ranged from 110.877 to
111.611 kH/s; these are four windows, not one continuous 240-second measurement.
The final public build reproduced the measured candidate's native library byte
for byte. Rates measure local completed work, not pool-side estimated hashrate,
payouts or earnings. The live session average includes startup and job waits.

The exact public package passed **124 production tests**, **15 tuning-tool tests**,
native self-test, **1,031 saved Rust-answer inputs through four C implementations**,
and **1,031 entire-scratchpad comparisons**. Saved answers were replayed; fresh
Rust was not executed. Each of **192 actual hugetlb workers** also returned a
reference-verified terminal hash with zero dropped shares.

The five-minute pool run recorded zero rejected, unresolved, locally stale,
duplicate or invalid shares, zero reconnects and zero queue drops. Native workers
closed normally. This is finite functional evidence on one machine. A full live
fee cycle, deliberate live reconnect recovery, long soak testing and a matched
**5% advantage over BzMiner remain unverified**. The selected profile is not a
universal fastest setting or a hashrate guarantee.

## What changed from beta.2

- Optimized two native arithmetic cases while retaining original fallbacks and
  hash behavior; the worker layout and disclosed fee policy are preserved.
- Production native-engine duplicate tracking now uses bounded lifetime nonce
  watermarks shared across jobs, reconnects and USER/FEE transitions. Reference
  verification still precedes submission.
- Added optional ordered `cpus` configuration, strict validation before native
  loading or networking, and an explicit 192-thread 7995WX hugetlb example.
- Added benchmark and worker-qualification tools, plus an interruption regression
  fix that closes a benchmark child-launch cleanup window.

## Build and run

Arrange Python 3.10+, **GCC 14** and GNU binutils through a trusted setup. Stop
any existing CPU miner normally first. Build as a normal user on the computer
that will mine: compilation uses `-march=native`, so the resulting library must
not be moved to a CPU with different instruction support.

After downloading the named archive and checksum to one directory:

```bash
sha256sum --check SHA256SUMS-beta.3-public-source-preview.1.txt &&
tar -xzf OverXelis-Miner-1.0.0-beta.3-public-source-preview.1.tar.gz &&
cd OverXelis-Miner-1.0.0-beta.3-public-source-preview.1
```

Use the actual absolute path of your GCC14 executable, then stop on any failure:

```bash
python3 -I -B build_public.py --compiler /absolute/path/to/gcc14 &&
python3 -I -B qualify_public.py &&
bash run.sh --self-test
```

Configure your own **public payout address**, pool and worker, review the settings,
then start foreground mining:

```bash
bash run.sh --configure
bash run.sh --check
bash run.sh --accept-dev-fee
```

Press **Ctrl+C** to stop. The generic example retains ordinary-memory settings;
`config.7995wx.example.json` is an optional 192-thread hugetlb profile requiring
huge pages and permissions already configured. Its public wallet placeholder
cannot start mining. No seed phrase, private key or exchange login is required.

Read the [complete source guide](miner/README.md), [packaging notes](miner/PUBLIC-PREVIEW-NOTES.md),
[security information](miner/SECURITY.md) and [release history](RELEASE-NOTES.md).
A checksum detects unexpected file changes; it is not a publisher signature.

## Preserved history and project scope

Beta.2 archives, tags and historical observations remain available. Its earlier
real fee transition and longer partial run are **beta.2 evidence**, not beta.3
qualification. See the [historical beta.2 report](https://froghollowfirewood.github.io/overxelis-miner/site-status.html#runtime-validation)
and [sanitized record](docs/evidence/preview2-early-ended-validation-20261029.json).
No comparison with a different miner from a different test window establishes
a current matched ranking.

The website is in `docs/`; auditable miner source is in `miner/`. The website does
not mine in browsers, accept payments, collect configuration fields or install
software automatically. No Windows, macOS, ARM, GPU or automatic service package
is supplied. Run only on computers you own or are authorized to use.

OverXelis is not affiliated with or endorsed by XELIS or Kryptex. Project code is
MIT licensed; third-party components retain their included notices and licenses.
