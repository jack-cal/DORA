# SUMUWW ordinary wallets

Update every validating full node and ordinary wallet before **block 9,600**. The connection-proof candidate certificate and renewal rules activate at that height. English is the first-launch language on every operating-system language; a saved language choice remains in effect.

[All components](../README.md) · [Installation and verification](../Documentation/COMPONENT_SUITE.md)

| Platform | Version | Download | Source |
|---|---|---|---|
| Windows | 1.0.8 | [Windows ZIP](https://github.com/jack-cal/SUMUWW/releases/tag/wallet-pc-v1.0.8) | [Desktop source](Desktop) |
| Android | 1.1.7 | [Signed APK](https://github.com/jack-cal/SUMUWW/releases/tag/wallet-android-v1.1.7) | [Android source](Source) |

Receive, send, review transactions, back up and restore existing encrypted wallets.
English is the first-launch default; 34 offline UI languages remain available.
These wallets validate and synchronize the blockchain locally and have no mining
controls. They are separate from the full-node/miner interface, not SPV clients.

Android 1.1.7 installs as **SUMUWW Wallet Current**, `org.sumuww.wallet.current`,
alongside the old wallet. It updates earlier Wallet Current versions signed with the same key in place. That key cannot update the old org.sumuww.wallet application
in place. Keep the old app and data; import an encrypted backup or recovery words
to retain the same address and ownership. Do not clear old app data. Legacy Android org.sumuww.wallet
versions 1.0.7–1.0.9 remain withdrawn; use the current app for current rules.

## Rules from block 9,000

The current rules apply at height **9,000 inclusive**. Blocks produced by legacy
software under the old rules at height 9,000 or above are rejected by upgraded
nodes and cannot extend the upgraded chain. Update miners and validating nodes.
Valid legacy blocks through **8,999 remain usable**, including the valid prefix
of a mixed synchronization batch. Wallet keys, valid coins, issuance and halvings
are preserved. Validation follows block rules, not an advertised version string.

Current editions, 26 October 2026: shared core 0.57.47, live local-queue fee previews, persistent replacement history, current reward information and documentation in all 34 supported languages. Android 1.1.7 is prepared as an APK; physical-phone testing and installation of this version are not claimed.
