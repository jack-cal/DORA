# SUMUWW Windows 0.57.38

Full node, wallet and optional CPU miner. This release includes the recent peer-recovery fixes and the All blocks browser.

## Changes

- Add an All blocks browser covering the locally validated active chain from genesis to tip, with height search and pagination. Mining screens retain the local miner's own progress.
- Keep verified peer contacts available across transient failures, correct double-counted failures, and preserve timeout failures instead of recording them as successes.
- Recover missing listener hints from fully synchronized inbound peers, then independently verify the candidate before using or sharing it. Identity deduplication and full chain validation still apply.
- Allow bounded 120-second public outgoing handshake and established response waits. Short partial-frame and write deadlines remain in place.
- Reuse matching, immutable validated ancestry prefixes and yield between background proof-history jobs to reduce network stalls.
- Retain all 34 UI languages, existing icons, wallets, balances and valid block history. English remains the default for new profiles and publication documents.

## Update

Extract the complete ZIP, close the previous application and run SUMUWW.exe with the existing data directory. Python is bundled. Windows executables do not have a publisher code-signing certificate.

Preserve existing wallets and chain data. Check PC-SHA256SUMS.txt before installing. English is the publication language; saved language preferences and all 34 UI languages are retained.

## Verification and remaining issue

80 Windows source tests, 20 physical-Android backend tests, one physical-phone history benchmark and six frozen Windows checks passed. Direct external synchronization and actual phone hashing were observed with the production PC application off.

External-peer availability is not guaranteed. During the physical-phone test with the PC app and temporary diagnostic nodes off, one established external connection ended after about five minutes. The verified peer count briefly became zero and synchronization recovered automatically after 13.39 seconds. No local response expiry or protocol rejection was recorded for that event. The remote/path-side termination remains internally undiagnosed; this release does not claim uninterrupted connectivity.

A new-block synchronization pause lasted 53.28 seconds, then hashing resumed automatically. This was a network synchronization wait, not signature collection. When the only reachable validated peer disappears, zero peers is reported until reconnection or another verified peer is available. Unknown or unvalidated data never receives mining readiness.

## Block-height compatibility

The height-9000 rules are unchanged: valid legacy blocks through 8999 remain usable, including the valid prefix of mixed synchronization batches. Blocks produced under incompatible old rules at height 9000 or above are rejected by upgraded nodes. Update miners and validating nodes; rejection depends on block rules, not the advertised application version.

Issuance, halvings, 20% connection-proof events and DGW adjustment every 10 blocks remain unchanged. Mining does not wait for witness signatures. The separate SMW/BTC conditional-spend activation remains at height 9100. P2P Full requires a synchronized, unpruned Bitcoin Core with txindex; P2P Light has its own SPV assumptions. This node update does not change either P2P edition.

## Downloads and source

[Program](https://github.com/jack-cal/SUMUWW/releases/download/pc-v0.57.38/SUMUWW-PC-0.57.38-English.zip) · [Source ZIP](https://github.com/jack-cal/SUMUWW/releases/download/pc-v0.57.38/SUMUWW-Windows-Source-0.57.38-English.zip) · [Detailed verification](https://github.com/jack-cal/SUMUWW/blob/main/Documentation/PEER_RECOVERY_VERIFICATION_0.57.38_0.6.88.md)


---

# SUMUWW Windows 0.57.34

Windows AMD64 full node, wallet and CPU miner. English is the default; all 34 UI languages remain available.

## Added and fixed

- Automatically prepare a fresh distributed-randomness key when the current beacon group cannot supply enough valid responses.
- Check participant health with authenticated threshold shares; retry withheld or invalid DKG contributions and unavailable prepared proposals.
- Bind each replacement to its exact predecessor and a round on the same PoW ancestry. Nodes independently validate the public setup and readiness signatures.
- Preserve completed historical proofs under their original key. Recovery does not block PoW mining or redraw old proof jobs.
- Preserve wallets, valid historical blocks, issuance, halvings, the 20% random event probability, cumulative-work priority and DGW/10 from height 9000.

- Show the scheduled height-9000 transition in all 34 languages: per-block DGW before activation, then adjustment every ten blocks.
- Correct Windows executable file-version metadata to 0.57.34 and reject stale version resources during builds.

## Verification

Eight independent process identities tested withholding, replacement, restart and late verification. Ten new recovery regression cases passed. The PC regression run passed 28 distinct cases across 36 executions, plus two numeric activation-prefix cases. Four UI/catalog tests covered all 34 languages. Six packaged executable checks passed after rebuilding.

## Download and update

[Windows ZIP](https://github.com/jack-cal/SUMUWW/releases/download/pc-v0.57.34/SUMUWW-PC-0.57.34-English.zip) · [Windows source ZIP](https://github.com/jack-cal/SUMUWW/releases/download/pc-v0.57.34/SUMUWW-Windows-Source-0.57.34-English.zip)

Extract the complete archive, close the previous program, and run SUMUWW.exe using the existing data directory. Keep the encrypted wallet and node database. The complete portable runtime is included; a separate Python installation is unnecessary. Windows executables do not have a publisher code-signing certificate. Check PC-SHA256SUMS.txt on the release page.

## Compatibility and scope

Recovery requires at least three usable participants, eventual delivery and a mined commitment. Old incomplete jobs may remain incomplete if their original threshold shares are lost. Validating nodes must upgrade before new recovery records are used. The protocol remains experimental; local checks are not an independent cryptographic audit or a multi-day public-network trial.
