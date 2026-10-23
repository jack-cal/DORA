# SUMUWW Android 0.6.88

Full node, wallet and optional CPU miner. This release includes the recent peer-recovery fixes and the All blocks browser.

## Changes

- Add an All blocks browser covering the locally validated active chain from genesis to tip, with height search and pagination. Mining screens retain the local miner's own progress.
- Keep verified peer contacts available across transient failures, correct double-counted failures, and preserve timeout failures instead of recording them as successes.
- Recover missing listener hints from fully synchronized inbound peers, then independently verify the candidate before using or sharing it. Identity deduplication and full chain validation still apply.
- Allow bounded 120-second public outgoing handshake and established response waits. Short partial-frame and write deadlines remain in place.
- Reuse matching, immutable validated ancestry prefixes and yield between background proof-history jobs to reduce network stalls.
- Retain all 34 UI languages, existing icons, wallets, balances and valid block history. English remains the default for new profiles and publication documents.

## Update

Package org.sumuww.miner, versionCode 148. Install over the existing matching full-node app without uninstalling or clearing data. The APK retains the original official signing lineage. Reopen the existing wallet after restart. The separate ordinary-wallet app is unchanged.

Preserve existing wallets and chain data. Check Android-SHA256SUMS.txt before installing. English is the publication language; saved language preferences and all 34 UI languages are retained.

## Verification and remaining issue

80 Windows source tests, 20 physical-Android backend tests, one physical-phone history benchmark and six frozen Windows checks passed. Direct external synchronization and actual phone hashing were observed with the production PC application off.

External-peer availability is not guaranteed. During the physical-phone test with the PC app and temporary diagnostic nodes off, one established external connection ended after about five minutes. The verified peer count briefly became zero and synchronization recovered automatically after 13.39 seconds. No local response expiry or protocol rejection was recorded for that event. The remote/path-side termination remains internally undiagnosed; this release does not claim uninterrupted connectivity.

A new-block synchronization pause lasted 53.28 seconds, then hashing resumed automatically. This was a network synchronization wait, not signature collection. When the only reachable validated peer disappears, zero peers is reported until reconnection or another verified peer is available. Unknown or unvalidated data never receives mining readiness.

## Block-height compatibility

The height-9000 rules are unchanged: valid legacy blocks through 8999 remain usable, including the valid prefix of mixed synchronization batches. Blocks produced under incompatible old rules at height 9000 or above are rejected by upgraded nodes. Update miners and validating nodes; rejection depends on block rules, not the advertised application version.

Issuance, halvings, 20% connection-proof events and DGW adjustment every 10 blocks remain unchanged. Mining does not wait for witness signatures. The separate SMW/BTC conditional-spend activation remains at height 9100. P2P Full requires a synchronized, unpruned Bitcoin Core with txindex; P2P Light has its own SPV assumptions. This node update does not change either P2P edition.

## Downloads and source

[Program](https://github.com/jack-cal/SUMUWW/releases/download/android-v0.6.88/SUMUWW-Android-0.6.88.apk) · [Source ZIP](https://github.com/jack-cal/SUMUWW/releases/download/android-v0.6.88/SUMUWW-Android-Source-0.6.88-English.zip) · [Detailed verification](https://github.com/jack-cal/SUMUWW/blob/main/Documentation/PEER_RECOVERY_VERIFICATION_0.57.38_0.6.88.md)
