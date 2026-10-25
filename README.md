# SUMUWW (SMW)

SUMUWW is an independent SHA-256d proof-of-work coin with asynchronous connection proofs. Valid cumulative work remains the primary chain-selection rule. Existing wallets, valid chain history, issuance and halvings are preserved.

## Current downloads — 25 October 2026

| Component | Version | Download | Source |
|---|---|---|---|
| Windows full node, wallet and miner | 0.57.46 | [Release](https://github.com/jack-cal/SUMUWW/releases/tag/pc-v0.57.46) | [Source](PC/Source) |
| Android full node, wallet and miner | 0.6.95 | [Release](https://github.com/jack-cal/SUMUWW/releases/tag/android-v0.6.95) | [Source](Android/Source) |
| Windows ordinary wallet | 1.0.6 | [Release](https://github.com/jack-cal/SUMUWW/releases/tag/wallet-pc-v1.0.6) | [Source](Wallet/Desktop) |
| Android ordinary wallet | 1.1.6 | [Release](https://github.com/jack-cal/SUMUWW/releases/tag/wallet-android-v1.1.6) | [Source](Wallet/Source) |
| Local block explorer | 0.4.10 | [Release](https://github.com/jack-cal/SUMUWW/releases/tag/explorer-v0.4.10) | [Source](Explorer/Source) |
| P2P Full — SMW/BTC trading | 0.3.4 | [Release](https://github.com/jack-cal/SUMUWW/releases/tag/p2p-full-v0.3.4) | [Source](P2P/Source) |
| P2P Light — SMW/BTC trading | 0.3.4 | [Release](https://github.com/jack-cal/SUMUWW/releases/tag/p2p-light-v0.3.4) | [Source](P2P/Source) |

[Current node documentation in 34 languages](https://github.com/jack-cal/SUMUWW/releases/tag/docs-20261025-r1) · [English whitepaper 2.2](https://github.com/jack-cal/SUMUWW/releases/tag/whitepaper-v2.2-en) · [Component installation guide](Documentation/COMPONENT_SUITE.md)

## Changes in these versions

Mining history and block APIs separate new issuance, transaction fees and total block rewards. Wallet-specific received amounts remain separate. Automatic fee previews use the connected node's current pending queue, block capacity and transaction priority; they do not sample past block fees or claim a view of every node. Manual rates and the final fee review remain available. One yugeon is 0.00000001 SMW.

The node exposes address validation, transaction decoding, signed-transaction checking and submission, UTXOs, confirmations, replacement status, reorganization state and ordered OP_RETURN data. The source examples cover disposable regtest submission and reorganization. Multisig and output-lock templates remain limited to explicitly activated isolated tests; public activation is not scheduled.

English is the default; all 34 existing UI languages and saved preferences are retained. Current program documentation is included in the matching packages. Read the [node specification](PC/Source/NODE_FEATURES.md), [current release status](Documentation/CURRENT_STATUS.md) and [verification record](Documentation/RELEASE_VERIFICATION_20261025.json).

Extract the complete Windows archive. Install each Android APK over the matching package signed with the same certificate; retain encrypted backups and application data. Android packages were prepared and inspected but these versions were not installed or tested on a physical phone. P2P Full requires synchronized unpruned Bitcoin Core with txindex; Light uses Bitcoin SPV and has different availability and trust limits. Both require the current SUMUWW node and the height-9100 HTLC rule.

Each component has a new release, matching source and SHA-256 checksums. Earlier release posts and attachments are preserved. Whitepaper 2.2 remains the existing published edition.

## Earlier node update: Windows 0.57.40 / Android 0.6.89

New proof jobs check responsiveness across the discovered identity inventory before selecting three witnesses. Valid replies survive retries and restarts; already selected jobs retain their original witnesses. PC public history shows all active-chain transactions and distinguishes nonselected lotteries, selected pending jobs, selected completed jobs and stored complete proofs. See the [repair verification and limits](Documentation/CONNECTION_PROOF_REPAIR_VERIFICATION.md). Completion still depends on the required participants being available.

## Previously published: Windows 0.57.38 / Android 0.6.88

[Windows 0.57.38 release](https://github.com/jack-cal/SUMUWW/releases/tag/pc-v0.57.38) and [Android 0.6.88 release](https://github.com/jack-cal/SUMUWW/releases/tag/android-v0.6.88) describe the previous published binaries.

Those packages introduced the All blocks browser, verified-contact recovery, corrected retry accounting, longer bounded waits for slow public peers and faster proof-history scheduling. Existing wallets, valid history and all 34 UI languages are retained.

**A remaining connection interruption was observed.** The phone synchronized and hashed with the PC app off, but its sole external connection closed once and recovered after 13.39 seconds. Uninterrupted connectivity is not claimed. See the [measured verification and limitations](Documentation/PEER_RECOVERY_VERIFICATION_0.57.38_0.6.88.md).

## SMW/BTC trading starts at SUMUWW block 9100

**Conditional exchange transactions are enabled from SUMUWW block 9100.** Both
P2P editions require a current synchronized local SUMUWW full node. Setup,
wallet creation and posting ads can happen earlier; they do not move coins or
bypass activation. Reaching 9100 alone does not guarantee a working trade.

**Full requires your own synchronized, unpruned Bitcoin Core with `txindex=1`.**
It downloads and retains Bitcoin history in addition to the trading application.
**Light does not require a local Bitcoin full node**; it verifies headers and
transaction inclusion proofs supplied by TLS servers and has different trust
and availability limits. Full and Light participants can trade with each other.

Read the **[Bitcoin full-node setup, disk requirements, Light setup and block-9100
guide](P2P/Source/BITCOIN_SETUP.md)** before funding. It explains configuration,
authentication, synchronization, operating costs, cancellation and recovery.

## Rules from block 9,000

The upgraded consensus rules apply at height **9,000 inclusive**. Blocks produced by legacy software under the old, pre-upgrade rules at height 9,000 or above are rejected by upgraded nodes and cannot extend the upgraded chain. Continued mining on a legacy branch does not make those blocks acceptable.

Valid historical blocks through **8,999 remain usable**, including the valid prefix of a mixed synchronization batch whose later legacy continuation is invalid. Existing wallets, coins, valid history, issuance and halvings are preserved. Update both miners and validating nodes before activation. This is validation by block rules, not a blanket rejection based only on an advertised software version.

## Protocol and documentation

[Whitepaper](Documentation/Whitepaper/WHITEPAPER.md) · [Connection proofs](Documentation/Whitepaper/CONNECTION_PROOFS_9000.md) · [Current verification](Documentation/CONNECTION_PROOF_REPAIR_VERIFICATION.md) · [Publication and document status](Documentation/CURRENT_STATUS.md)

The original issuance and halving schedule is preserved. Valid history through 8999 remains usable. From 9000, every block requires a producer-key commitment; random connection events use a 20% probability, and DGW recalculates every ten blocks with a 24-block observation window. Completed signatures are not a mining or block-acceptance prerequisite. The exact-template HTLC spending rule activates at 9100.

English is the publication language and the default for a fresh app profile. All 34 UI languages remain selectable. Saved language preferences are preserved, and document menus open the English edition.

## Release status

These node packages publish the post-PoW design described above, with the recorded local and isolated-network checks. They do not establish independent security certification, network-wide adoption, worldwide candidate discovery or irreversible finality. Read-only local checks on 24 October observed an active chain beyond height 9100. Read the specific limitations in the verification report and specification.

Previously withdrawn node releases remain withdrawn; the [withdrawal record](Archive/withdrawal-20261020/README.md) is retained. New [ordinary wallets](Wallet/README.md), [Explorer](Explorer/README.md) and [P2P](P2P/README.md) use the current shared core. Withdrawn older wallet binaries remain withdrawn. See [component changes, migration and verification limits](Documentation/COMPONENT_SUITE.md).

[Automatic beacon recovery](Documentation/BEACON_RECOVERY.md) is included in this release.

[Wallet, P2P and explorer fixes: UI, language and physical-device verification](Documentation/UI_LANGUAGE_VERIFICATION.md).
