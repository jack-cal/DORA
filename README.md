# SUMUWW (SMW)

SUMUWW is an independent SHA-256d proof-of-work coin with an experimental asynchronous connection-proof system. A block producer requests three witness signatures after PoW, binds the six signature halves to an exact parent/child pair, and relays completed evidence without making mining wait. Valid cumulative work remains the primary chain-selection rule.

## Downloads

| Component | Version | Release | Source |
|---|---|---|---|
| Windows node, wallet and miner | 0.57.33 | [Windows release](https://github.com/jack-cal/SUMUWW/releases/tag/pc-v0.57.33) | [PC source](PC/Source) |
| Android node, wallet and miner | 0.6.83 | [Android release](https://github.com/jack-cal/SUMUWW/releases/tag/android-v0.6.83) | [Android source](Android/Source) |
| Whitepaper and technical references | v2, English | [Whitepaper release](https://github.com/jack-cal/SUMUWW/releases/tag/whitepaper-v2.0-en) | [Editable documents](Documentation/Whitepaper) |

Read the component instructions and SHA-256 checksums before installing. Keep existing encrypted wallets and chain data. An Android update is installed over the existing app; do not uninstall or clear data.

## Protocol and documentation

[Whitepaper](Documentation/Whitepaper/WHITEPAPER.md) · [Connection proofs](Documentation/Whitepaper/CONNECTION_PROOFS_9000.md) · [Verification](Documentation/VERIFICATION.md)

The original issuance and halving schedule is preserved. Valid history through 8999 remains usable. From 9000, every block requires a producer-key commitment; random connection events use a 20% probability, and DGW recalculates every ten blocks with a 24-block observation window. Completed signatures are not a mining or block-acceptance prerequisite. The exact-template HTLC spending rule activates at 9100.

English is the publication language and the default for a fresh app profile. All 34 UI languages remain selectable. Saved language preferences are preserved, and document menus open the English edition.

## Release status

These node packages publish the post-PoW design described above, with the recorded local and isolated-network checks. They do not establish independent security certification, completed public-network activation, worldwide candidate discovery or irreversible finality. Read the specific limitations in the verification report and specification.

Previously withdrawn node releases remain withdrawn; the [withdrawal record](Archive/withdrawal-20261020/README.md) is retained. The separate [standalone wallet](Wallet/README.md) has not been rebuilt or reinstated. [Explorer](Explorer/README.md) and [P2P](P2P/README.md) remain separate applications.
