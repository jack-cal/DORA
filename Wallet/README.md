# SUMUWW ordinary wallets

[All components](../README.md) · [Installation and verification](../Documentation/COMPONENT_SUITE.md)

| Platform | Version | Download | Source |
|---|---|---|---|
| Windows | 1.0.2 | [Windows ZIP](https://github.com/jack-cal/SUMUWW/releases/tag/wallet-pc-v1.0.2) | [Desktop source](Desktop) |
| Android | 1.1.2 | [Signed APK](https://github.com/jack-cal/SUMUWW/releases/tag/wallet-android-v1.1.2) | [Android source](Source) |

Receive, send, review transactions, back up and restore existing encrypted wallets.
English is the first-launch default; 34 offline UI languages remain available.
These wallets validate and synchronize the blockchain locally and have no mining
controls. They are separate from the full-node/miner interface, not SPV clients.

Android 1.1.2 installs as **SUMUWW Wallet Current**, `org.sumuww.wallet.current`,
alongside the old wallet. It updates Wallet Current 1.1.0 or 1.1.1 in place with the same
signing key. That key cannot update the old org.sumuww.wallet application
in place. Keep the old app and data; import an encrypted backup or recovery words
to retain the same address and ownership. Do not clear old app data. Old standalone
wallet versions 1.0.7–1.0.9 remain withdrawn; use the current app for current rules.

## Rules from block 9,000

The current rules apply at height **9,000 inclusive**. Blocks produced by legacy
software under the old rules at height 9,000 or above are rejected by upgraded
nodes and cannot extend the upgraded chain. Update miners and validating nodes.
Valid legacy blocks through **8,999 remain usable**, including the valid prefix
of a mixed synchronization batch. Wallet keys, valid coins, issuance and halvings
are preserved. Validation follows block rules, not an advertised version string.

Release editions 2026-10-24: ordinary wallets now include core 0.57.38 connection
recovery and synchronization fixes. The wallet downloads are separate releases. Previously published full-node binaries are unchanged.
