# 1.0.0-beta.2 / public-source-preview.1

Experimental Linux x86-64 CPU **source preview**, not a stable release or universal binary.

This package carries forward the selected round-specialized hashing sources,
corrected symbol mapping and strict link checks, and the rig-edition transport
recovery safeguard. The new public launcher allows a user's own wallet, pool,
worker name, thread count, and ordinary/hugetlb memory mode. It runs as a normal
user in the foreground, refuses root for mining, and installs no service.

## Fee disclosure

99 active USER minutes precede a developer window of up to 60 seconds including
connection setup. Failed fee connections are skipped without catch-up. Restart
resets this beta's schedule. This is mining-time allocation, not a withdrawal or
an exact percentage of coins. See the guide for the fixed developer destination.

## Read before running

Build on the computer that will mine. Check SHA256SUMS.txt, then follow the guide.
A checksum is not a publisher signature. No Windows, macOS, ARM or GPU build is
provided. The public wrapper's live operation, non-root huge-page permissions
across systems, the complete real fee cycle, and long-term reliability remain
unverified. See VALIDATION.json for the actual checks, not an inferred success.

Never enter a seed phrase or private key. Do not blindly bypass security warnings.
The retained duplicate-input cache intentionally stops at 32,768 entries. The
normal-user public package is separate from the maintainer's private rig services.

Feedback is welcome via the bug and benchmark forms. Redact private information.
