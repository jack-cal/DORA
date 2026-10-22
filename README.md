# SUMUWW (SMW)

SUMUWW is an independent SHA-256d proof-of-work coin with an experimental asynchronous connection-proof system. A block producer requests three witness signatures after PoW, binds the six signature halves to an exact parent/child pair, and relays completed evidence without making mining wait. Valid cumulative work remains the primary chain-selection rule.

## Downloads

| Component | Version | Release | Source |
|---|---|---|---|
| Windows node, wallet and miner | 0.57.34 | [Windows release](https://github.com/jack-cal/SUMUWW/releases/tag/pc-v0.57.34) | [PC source](PC/Source) |
| Android node, wallet and miner | 0.6.84 | [Android release](https://github.com/jack-cal/SUMUWW/releases/tag/android-v0.6.84) | [Android source](Android/Source) |
| Windows ordinary wallet | 1.0.0 | [Windows wallet](https://github.com/jack-cal/SUMUWW/releases/tag/wallet-pc-v1.0.0) | [Source](Wallet/Desktop) |
| Android ordinary wallet | 1.1.0 | [Android wallet](https://github.com/jack-cal/SUMUWW/releases/tag/wallet-android-v1.1.0) | [Source](Wallet/Source) |
| Local block explorer | 0.4.5 | [Explorer](https://github.com/jack-cal/SUMUWW/releases/tag/explorer-v0.4.5) | [Source](Explorer/Source) |
| P2P order sharing and regtest exchange | 0.1.8 | [P2P](https://github.com/jack-cal/SUMUWW/releases/tag/p2p-v0.1.8) | [Source](P2P/Source) |
| Whitepaper and technical references | v2.1, English | [Whitepaper release](https://github.com/jack-cal/SUMUWW/releases/tag/whitepaper-v2.1-en) | [Editable documents](Documentation/Whitepaper) |

Read the component instructions and SHA-256 checksums before installing. Keep existing encrypted wallets and chain data. Android full-node updates install over the matching existing app. The new ordinary Android wallet installs alongside the old wallet and imports an encrypted backup; do not uninstall or clear old app data. See the [component suite guide](Documentation/COMPONENT_SUITE.md).

## Upgrade before block 9,000

The upgraded consensus rules apply at height **9,000 inclusive**. Blocks produced by legacy software under the old, pre-upgrade rules at height 9,000 or above are rejected by upgraded nodes and cannot extend the upgraded chain. Continued mining on a legacy branch does not make those blocks acceptable.

Valid historical blocks through **8,999 remain usable**, including the valid prefix of a mixed synchronization batch whose later legacy continuation is invalid. Existing wallets, coins, valid history, issuance and halvings are preserved. Update both miners and validating nodes before activation. This is validation by block rules, not a blanket rejection based only on an advertised software version.

## Protocol and documentation

[Whitepaper](Documentation/Whitepaper/WHITEPAPER.md) · [Connection proofs](Documentation/Whitepaper/CONNECTION_PROOFS_9000.md) · [Verification](Documentation/BEACON_RECOVERY_VERIFICATION.md)

The original issuance and halving schedule is preserved. Valid history through 8999 remains usable. From 9000, every block requires a producer-key commitment; random connection events use a 20% probability, and DGW recalculates every ten blocks with a 24-block observation window. Completed signatures are not a mining or block-acceptance prerequisite. The exact-template HTLC spending rule activates at 9100.

English is the publication language and the default for a fresh app profile. All 34 UI languages remain selectable. Saved language preferences are preserved, and document menus open the English edition.

## Release status

These node packages publish the post-PoW design described above, with the recorded local and isolated-network checks. They do not establish independent security certification, completed public-network activation, worldwide candidate discovery or irreversible finality. Read the specific limitations in the verification report and specification.

Previously withdrawn node releases remain withdrawn; the [withdrawal record](Archive/withdrawal-20261020/README.md) is retained. New [ordinary wallets](Wallet/README.md), [Explorer](Explorer/README.md) and [P2P](P2P/README.md) use the current shared core. Withdrawn older wallet binaries remain withdrawn. See [component changes, migration and verification limits](Documentation/COMPONENT_SUITE.md).

[Automatic beacon recovery](Documentation/BEACON_RECOVERY.md) is included in this release.
