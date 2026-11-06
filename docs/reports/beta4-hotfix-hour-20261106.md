# Beta.4 hotfix: logged hour of continuity — 6 November 2026

The development hotfix ran real Kryptex work with 192 workers, all using huge pages. After excluding 60 seconds of startup and the first display interval that crossed that boundary, the retained measurement covers **3,627.494905 seconds (60 minutes 27.49 seconds)**. The process subsequently logged a requested stop and normal closure of all native workers.

| Recorded measure | Result |
| --- | ---: |
| Rounded local display intervals | 361 |
| Unweighted display mean | 119.739756 kH/s |
| Minimum / maximum displayed interval | 119.517 / 119.978 kH/s |
| Population standard deviation of displays | 0.071353 kH/s |
| Accepted USER shares in the measured interval | 444 (counter 6 to 450) |
| Full-session accepted USER / FEE shares | 450 / 0 |
| Maximum displayed rejected / unresolved | 0 / 0 |
| Final full-session local display | 119.728 kH/s |

These are rounded local console observations, **not an exact raw completed-hash counter measurement**, a pool-side estimate or an earnings result. An average is not a sustained minimum: the sampled minimum was below 120 kH/s. No continuous sub-interval minimum between displays can be established.

## Method and continuity

The session began at 22:18:33.741532 UTC. The fixed 60-second warmup ended at 22:19:33.741532 UTC. The first later status, 22:19:34.185316, supplies the start boundary; its own displayed rate is excluded because its preceding interval crossed warmup. The next 361 hashing displays end at 23:20:01.680221 UTC. The final paused display at 23:20:03.746353 is excluded from the performance average. All retained statuses report USER mode and hashing; the maximum interval between statuses is 10.100135 seconds. The log contains one connection and one authorization, with no logged reconnect or crash marker. This does not test reconnect recovery.

Shutdown accounting reports 3,689.491 active USER seconds, zero active FEE seconds and zero fee windows. Its `Skipped: 0` means skipped **fee windows**, not skipped undefined native nonces. The run ended before the scheduled 99-minute USER-to-FEE transition. It therefore does not qualify a full fee cycle.

The earlier private continuity summary used 363 post-cutoff displays, including the warmup-crossing interval and the final paused status. This report independently recomputes a stricter 361-interval performance series; the original summary is preserved.

## Build identity and conditions

Hardware: AMD Threadripper PRO 7995WX; 192 workers; 192/192 huge-page workers. The retained build record identifies GCC 15.2.0, with PGO disabled. GPU activity, cooling settings and temperatures were not recorded for this session and must not be inferred from the separate short GPU-on tests.

The development launcher still printed `1.0.0-beta.4 / public-source-preview.1`. Its repaired native library matches the library qualified from the current public preview-2 package **byte for byte**:

```text
e519d8b10619776a16db50252f41b0fd70f300d0e2b05633577249cc9874faa9
```

A separately saved continuity record pins this same hash and the completed process identity. The installed library's modification and change timestamps predate the session; the selected native source hashes also match the qualified hotfix. This supports the native hotfix association rather than relying on the banner. A per-run loaded-library inode attestation was not saved. This is a **development-hotfix native continuity observation**, not an hour-long run of the exact preview-2 launcher edition or a beta.5 candidate.

The public source remains commit `d7ac5a593f0663b75f0cc08f6d3e18e0d42dc772`. Its unchanged named archive SHA-256 is:

```text
4ede37b957b5024611f63714f4593bd60a849c0dd9c14594490353c56bdb53da
```

## Missing measurements and limits

Raw completed-work counter boundaries and a monotonic performance interval were not saved for this hour. Native queue-drop and undefined-nonce skip counters, first-failure capture state, and separate local stale/duplicate/invalid counters were not sampled. Zero rejected and unresolved displays do not establish zeros for those unmeasured categories. No zero-native-skip or queue-drop claim is made for this hour.

The original cause of the zero intermediate remains unverified. One logged hour does not establish long-term stability, elimination of every crash cause, portability, a full fee cycle or a matched advantage over another miner. The historical 121.157224 kH/s GPU-paused hour remains evidence of the **unpatched** build. The two earlier hotfix counter-based short results, 119.302920 and 118.955001 kH/s, remain separate observations with different measurement methods.

The [sanitized data](../evidence/beta4-hotfix-hour-continuity-20261106.json) contains the 361 rounded rates, wall-clock interval lengths and accepted-share deltas, plus hashes of the private source evidence. It contains no raw private log, worker identity, payout address or configuration. Existing source archives, tags, release assets and preparation-time validation records have not been regenerated.
