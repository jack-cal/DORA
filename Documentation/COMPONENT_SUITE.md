# SUMUWW component suite — 25 October 2026

| Component | Version | Download | Source |
|---|---|---|---|
| Windows full node, wallet and miner | 0.57.46 | [Release](https://github.com/jack-cal/SUMUWW/releases/tag/pc-v0.57.46) | [Source](../PC/Source) |
| Android full node, wallet and miner | 0.6.95 | [Release](https://github.com/jack-cal/SUMUWW/releases/tag/android-v0.6.95) | [Source](../Android/Source) |
| Windows ordinary wallet | 1.0.6 | [Release](https://github.com/jack-cal/SUMUWW/releases/tag/wallet-pc-v1.0.6) | [Source](../Wallet/Desktop) |
| Android ordinary wallet | 1.1.6 | [Release](https://github.com/jack-cal/SUMUWW/releases/tag/wallet-android-v1.1.6) | [Source](../Wallet/Source) |
| Local block explorer | 0.4.10 | [Release](https://github.com/jack-cal/SUMUWW/releases/tag/explorer-v0.4.10) | [Source](../Explorer/Source) |
| P2P Full — SMW/BTC trading | 0.3.4 | [Release](https://github.com/jack-cal/SUMUWW/releases/tag/p2p-full-v0.3.4) | [Source](../P2P/Source) |
| P2P Light — SMW/BTC trading | 0.3.4 | [Release](https://github.com/jack-cal/SUMUWW/releases/tag/p2p-light-v0.3.4) | [Source](../P2P/Source) |

## Installation and existing data

Extract each complete Windows ZIP. Keep encrypted wallet backups and existing data directories. Ordinary wallets validate and synchronize the chain locally; Explorer reads a selected node database without changing it. The full-node/miner applications and ordinary wallets have separate interfaces and profiles.

Android full node 0.6.95 uses org.sumuww.miner. Android ordinary wallet 1.1.6 uses org.sumuww.wallet.current and retains its signing certificate. It can update earlier matching Wallet Current installations. It does not replace the old differently signed org.sumuww.wallet app. Keep the old app and its data until an encrypted backup has been restored successfully. Both new APKs are installation files; physical-phone testing and installation are not claimed.

P2P Full requires synchronized unpruned Bitcoin Core with txindex. Light verifies Bitcoin headers and transaction inclusion using TLS servers and is not full Bitcoin validation. Both require a synchronized SUMUWW node and the height-9100 HTLC rule. Read the [setup and recovery guide](../P2P/Source/BITCOIN_SETUP.md).

## Current behavior and verification

The shared core is 0.57.46. Fees use live local pending-queue observations. Block issuance, fees and total rewards are reported separately; wallet-specific received amounts are not confused with block totals. Transaction replacement records survive restart. The node exposes signed-transaction checks/submission, chain queries and ordered data records. The source reference does not hold private keys or provide a separate signing application.

Multisig/output-lock validation is available only for explicitly activated isolated tests. No public activation is scheduled. Existing public-network consensus, wallet formats, issuance and halvings are preserved. The current height-9000 rules and the separate height-9100 HTLC rule still apply.

English remains the default and all 34 existing UI languages and language preferences are retained. [Current multilingual notes](Node-Features-46-95/index.html) and [verification record](RELEASE_VERIFICATION_20261025.json) describe the tested scope. Windows binaries are not publisher-code-signed. No independent security audit or uninterrupted public-network availability is claimed.

Earlier release posts, files and dated verification reports retain their original scope. Whitepaper 2.2 remains the published whitepaper edition.
