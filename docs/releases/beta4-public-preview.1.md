# OverXelis Miner 1.0.0-beta.4 · public-source-preview.1

Experimental Linux x86-64 XelisHashV3 CPU miner. **Source only**: build and
qualify it on the computer that will mine. No precompiled miner or private
configuration is included.

## Release assets

Download `OverXelis-Miner-1.0.0-beta.4-public-source-preview.1.tar.gz` and
`SHA256SUMS-beta.4-public-source-preview.1.txt`. The archive is **309,121 bytes**
and contains 68 tracked source files plus their manifest.

```text
SHA-256: 7c0e9bf745d22c86bf186e360ed2a8cc23ec5bdb7e188adf4fd1c7a4a24c5cd4
```

Also read the attached `BETA4-PUBLIC-VALIDATION-NOTES.md` for current build
instructions and the frozen internal documentation caveat.

Use these named assets rather than GitHub's automatic source ZIP. A checksum
checks integrity; it is not a publisher signature.

## Recorded result: GPU mining paused and Mining100 cooling

**On one Threadripper PRO 7995WX, 192 hugetlb workers, GCC 15.2.0, ordinary
non-PGO build, GPU mining paused and all six fan channels on Mining100**, the
hour test recorded **121.157224 kH/s mean displayed Local rate** and a
**120.908 kH/s minimum** across 366 counted samples. After a 600-second settling
period, conservative active USER coverage was 3,671.545 seconds, with
**393 accepted USER shares and zero rejected/unresolved work**. No counted
pause, reconnect or error was recorded, and the miner shut down normally.

This mean is an unweighted average of rounded Local display samples, not an
independent raw-counter hour rate, pool-side hashrate estimate or earnings
measurement. CPU clock/voltage settings were unchanged. A separate GPU-on
attempt failed the strict displayed 120 kH/s minimum; the passing result is
specific to the GPU-paused/cooling conditions above.

Separate real Kryptex desktop runs on the same artifact and conditions measured
23.844454 kH/s at 24 workers over 311.380 seconds and 31.786244 kH/s at 32 workers
over 311.512 seconds, using completed-hash counts after at least 60 seconds of
settling. They accepted 3 and 13 USER shares respectively, with zero
rejected/unresolved work. These are shorter profiles, not hour results.

Three other CPU rigs rebuilt and qualified the source at 32/24/24 workers using
GCC 13.3.0/13.3.0/11.4.0 and verified accepted Kryptex startup work. Their existing
configuration and service policies were preserved, with no GPU changes reported.
That is portability/startup evidence, not sustained speed on those rigs.

## Changes and use

The selected kernel revises exact arithmetic, index folding, shared tails and
guarded square-root estimates, and includes the selected folded-A salt
expression/compiler barrier. Full qualification checks 1,031 saved Rust-answer
inputs through four C implementations and entire reference scratchpads. The
runtime, configuration format and **1% scheduled developer-time policy** are
preserved: 99 active USER minutes, then a FEE window of up to 60 seconds.

Use Python 3.10+, GNU binutils and an existing trusted GCC. GCC 15.2 was used for
the recorded desktop profile. Compile locally with strict math, run
`qualify_public.py` and the native self-test, configure your public payout and
pool settings, then mine with `--accept-dev-fee`. Stop on any failed check.
See the [README](https://github.com/FrogHollowFirewood/overxelis-miner/blob/main/README.md)
and [sanitized evidence](https://github.com/FrogHollowFirewood/overxelis-miner/blob/main/docs/evidence/beta4-validation-20261106.json).

The archive's internal README and VALIDATION.json describe an earlier development
checkpoint, including older kernel hashes and an earlier 118 kH/s plan. The
current dated report for source manifest `90ca3e0d…` and tested desktop native
`f5072ba1…` supersedes those validation descriptions. The attached addendum gives
full identities and current build instructions. Development STAGING-METADATA
mentioned internally is not shipped or needed to build. No universal or GPU-on
120 kH/s promise, matched 5% BzMiner advantage, completed beta.4 fee cycle or
deliberate live reconnect-recovery test is claimed. Earlier releases and their
historical evidence remain available.
