## Beta.4 crash fix — public source preview 2

This prerelease supersedes beta.4 public source preview 1, which can stop with an integer division-by-zero fault reported by the shell as “floating point exception.” Upgrade to this named source archive and qualify the build locally.

The selected production hash path now rejects a zero round modulus before division or digest finalization. The worker consumes that nonce, excludes it from completed-work counts and share queues, and continues with subsequent work. No substitute hash is generated. A separate skip counter and first-input capture are available in native runtime memory for diagnostics; the public launcher does not automatically persist that input.

The historical failing input was not retained, so the origin of its zero intermediate state remains unverified. Reference/experimental kernels retain their earlier zero-modulus behavior; legacy void selected calls deliberately trap on failure. This repair protects the observed selected production path and does not establish that all possible crashes are eliminated.

## Download and build

Use `OverXelis-Miner-1.0.0-beta.4-public-source-preview.2.tar.gz` and `SHA256SUMS-beta.4-public-source-preview.2.txt` under Assets. This is source-only: no native binary, private configuration or compiler is included. The automatic GitHub source ZIP is a different archive. Build as a normal user on the mining computer with Python 3.10+, a trusted GCC 15 and GNU binutils, then run the included qualification and self-test in the documented order.

Archive SHA-256: `4ede37b957b5024611f63714f4593bd60a849c0dd9c14594490353c56bdb53da`

## Validation and measurement scope

The release validation notes and sanitized JSON identify the exact package, its build and correctness checks. The hotfix native library recorded two short real-Kryptex windows on one Threadripper PRO 7995WX with 192 hugetlb workers, GCC 15.2 non-PGO, and GPU mining running: 119.302920 kH/s over 191.063907 seconds and 118.955001 kH/s over 190.778115 seconds after settling, with 25 and 28 accepted USER shares in those windows. Both reported zero rejected, unresolved or queue-dropped shares.

The earlier 121.157224 kH/s GPU-paused hour belongs to unpatched preview 1 and does not qualify this hotfix. No new hotfix hour, long soak, complete fee cycle, deliberate reconnect exercise, broader hardware ranking or universal 120 kH/s guarantee is claimed. The beta.5 140 kH/s goal is not a result of this release.

The disclosed 1% scheduled developer mining-time allocation and configuration behavior are unchanged. Stop an existing CPU miner or test normally before building, qualifying or starting another.
