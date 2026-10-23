# Verification: Windows 0.57.38 / Android 0.6.88

23 October 2026. This report covers the packaged client corrections and a bounded physical-phone observation, not an independent security audit or a long-running availability guarantee.

## Changes

- Add an All blocks browser covering the locally validated active chain from genesis to tip, with height search and pagination. Mining screens retain the local miner's own progress.
- Keep verified peer contacts available across transient failures, correct double-counted failures, and preserve timeout failures instead of recording them as successes.
- Recover missing listener hints from fully synchronized inbound peers, then independently verify the candidate before using or sharing it. Identity deduplication and full chain validation still apply.
- Allow bounded 120-second public outgoing handshake and established response waits. Short partial-frame and write deadlines remain in place.
- Reuse matching, immutable validated ancestry prefixes and yield between background proof-history jobs to reduce network stalls.
- Retain all 34 UI languages, existing icons, wallets, balances and valid block history. English remains the default for new profiles and publication documents.

## Evidence and checks

| Check | Result |
|---|---|
| Windows source regressions | 80 tests passed: public reply deadlines, partial frames, freshness, cache invalidation, identity, discovery, retry accounting, synchronization and mining fairness. |
| Physical Android backend | 20 tests passed inside an isolated audit application; the audit app was removed afterwards. |
| Physical Android history benchmark | One additional test passed against an actual validated 9037-block history snapshot. |
| Frozen Windows programs | Six isolated checks passed, including two-node block/transaction relay and encrypted-wallet backup/restore. The production PC node stayed off. |
| Packaged Python | All eight Python archives in the tested Android audit APK matched the signed production APK. |
| Existing data | Android was updated in place with the original signing lineage; the user opened the existing wallet. Block 9037 retained its prior hash. All 9,128 existing PC block records and the encrypted PC wallet file were unchanged. |
| Phone without PC | Direct external synchronization reached height 9042; block 9042 came from another producer. |
| Actual mining | 91,992,064 hash attempts and 186.86 seconds of hashing over a 252.46-second run. One network pause of 53.28 seconds; automatic resumption verified. No new local PoW block was found during this short run. Test mining was stopped; the final state had one validated external peer. |
| UI and languages | Existing 34-language resources retained. Wallet opening, mining start/stop, statistics and historical-block search exercised. A full language/button matrix was not repeated for the latest network patch. |

Read-only TCP probes observed first version replies after 25.078 and 59.453 seconds, beyond the former five-second outgoing handshake deadline. On the same PC, 18 historical parent lookups on the real snapshot decreased from 7.132 seconds to 0.000658 seconds. The corrected 18-lookup batch took 0.009327 seconds on the physical phone. These are bounded measurements, not universal performance claims. SQLite snapshot changes and alternate branches invalidate or bypass prefix reuse.

## Remaining limitations

External-peer availability is not guaranteed. During the physical-phone test with the PC app and temporary diagnostic nodes off, one established external connection ended after about five minutes. The verified peer count briefly became zero and synchronization recovered automatically after 13.39 seconds. No local response expiry or protocol rejection was recorded for that event. The remote/path-side termination remains internally undiagnosed; this release does not claim uninterrupted connectivity.

A new-block synchronization pause lasted 53.28 seconds, then hashing resumed automatically. This was a network synchronization wait, not signature collection. When the only reachable validated peer disappears, zero peers is reported until reconnection or another verified peer is available. Unknown or unvalidated data never receives mining readiness.

## Compatibility

The height-9000 rules are unchanged: valid legacy blocks through 8999 remain usable, including the valid prefix of mixed synchronization batches. Blocks produced under incompatible old rules at height 9000 or above are rejected by upgraded nodes. Update miners and validating nodes; rejection depends on block rules, not the advertised application version.

Issuance, halvings, 20% connection-proof events and DGW adjustment every 10 blocks remain unchanged. Mining does not wait for witness signatures. The separate SMW/BTC conditional-spend activation remains at height 9100. P2P Full requires a synchronized, unpruned Bitcoin Core with txindex; P2P Light has its own SPV assumptions. This node update does not change either P2P edition.

## Installation and files

Use the versioned Windows ZIP or signed Android APK and compare the SHA-256 digest in the corresponding release. Keep encrypted-wallet backups and existing chain data. Close the old Windows application before replacing its program folder. Install Android over the matching existing application; do not uninstall or clear data. Reopen the existing wallet after restart.

Source archives accompany each platform release. Personal wallet files, chain databases, signing keys and raw device/network logs are not release assets.
