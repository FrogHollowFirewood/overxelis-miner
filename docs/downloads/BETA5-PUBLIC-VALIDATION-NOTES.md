# OverXelis Miner beta.5 public source preview 1

This source preview is based on the beta.5 warm-handoff development build used in the completed Kryptex trial. Build and qualify the source on the Linux x86-64 computer that will mine. The source archive ships with example configurations and verification tools.

## Completed Kryptex development trial

The trial ran from November 7 to November 9, 2026, Central Standard Time, on one AMD Threadripper PRO 7995WX with 192 workers and 192 verified huge-page allocations.

| Measure | Recorded result |
| --- | ---: |
| Wall-clock duration | 33 hours, 31 minutes, 18 seconds |
| Miner-displayed session average | 124.060 kH/s |
| Accepted user shares | 13,911 |
| Accepted developer fee shares | 137 |
| Rejected shares | 0 |
| Unresolved submissions | 13 |
| Peak CPU sensor reading | 83.875 °C |
| Trial launcher CPU cutoff | 85 °C |

The launcher recorded zero thermal cutoffs, and all native workers closed normally after a requested stop. The 13 unresolved submissions were recorded during connection interruptions. The run log does not establish their root cause. The 85 °C cutoff belongs to the trial launcher.

The 124.060 kH/s figure is the miner's local session display. The trial did not save a completed-hash counter window or measure pool-side hashrate or CPU package power. It establishes a real-pool observation for this build and desktop. A matched speed gain, a power comparison, and the 140 kH/s target remain unqualified.

## Original build provenance

The desktop trial used GCC 15.2.0 without profile-guided optimization. Its launcher still displayed the inherited beta.4 preview 1 banner. The development build's pinned identities were:

| Trial component | SHA-256 |
| --- | --- |
| Source manifest | `3dab34f06bb8a5b7698ee9800bca18f41ea20d3eed982eef90784c3b67d92598` |
| Native library | `b4a5963177c96016fbfb4b90e672f8e4eddc2ed7bdcc2618ef236f78af8e0a8f` |
| Build record | `8444bd62a91110806df1516f565db4eee89085e599ef34e2311afcfa27d178b6` |

The pinned native library replayed 1,031 saved Rust-answer cases through four C implementations, including 1,031 full scratchpad comparisons. The offline development suite recorded 137 passing tests, including 46 fee tests. Saved answers were replayed without executing Rust on the desktop.

The 33-hour measurement belongs to this original development session. Rebuild and qualify the public source locally before mining. The separate Stage 3 round-one scratchpad patch is excluded from this preview. It passed offline correctness checks and awaits desktop qualification and a matched Kryptex test.

## Public archive verification

- Archive size: 315,297 bytes
- Archive SHA-256: `1c75f85aa9aba08abe3cd34fdc15aaceb1059c2292f3835c9c45e5b087c6678b`
- Public source manifest SHA-256: `27bf32a739e56692251601b474f342f91fdeba09a78869437cabacb5625dd17d`
- Isolated GCC 14.2.0 rebuild library SHA-256: `72c6da6b51d821f3a6aa4aabd94fe07befc4b5d63ebd473d71be2ee827016259`

A fresh extraction passed 139 offline tests, native self-test, 1,031 saved Rust
answers across four C paths, and 1,031 full scratchpad comparisons. Forced-zero
tests in both rounds passed with one ordinary-page worker. Each test consumed
the failed nonce without counting a completed hash or queuing a share.

These checks ran offline on a separate host using GCC 14.2.0. The 192-worker
desktop trial used GCC 15.2.0. Use a trusted GCC 15 for the documented build and
qualify the result on the mining host. The public repack has separate source
and library identities.
