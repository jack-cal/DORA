# SUMUWW component suite — 2026-10-24

| Application | Version | Purpose |
|---|---|---|
| Windows full node | 0.57.40 | Validation, synchronization, wallet and optional mining |
| Android full node | 0.6.89 | Validation, synchronization, wallet and optional mining |
| Windows ordinary wallet | 1.0.2 | Receiving, sending, backup, recovery and activity |
| Android ordinary wallet | 1.1.2 | Receiving, sending, backup, recovery and activity |
| Explorer | 0.4.6 | Read-only local blockchain inspection |
| P2P Full | 0.3.0 | SMW/BTC board and settlement using local full nodes |
| P2P Light | 0.3.0 | SMW/BTC board and settlement using Bitcoin SPV |

Windows full node 0.57.40 includes public block/transaction browsing and the connection-proof availability repair. Android full node 0.6.89 includes the same proof repair. New jobs probe all discovered identities before selecting three responsive witnesses; old selected jobs keep their original witnesses. Valid replies survive retries and restarts. Setup records, local lottery jobs and complete proofs have distinct counters. Full-node release pages: [PC 0.57.40](https://github.com/jack-cal/SUMUWW/releases/tag/pc-v0.57.40) and [Android 0.6.89](https://github.com/jack-cal/SUMUWW/releases/tag/android-v0.6.89). Wallet 1.0.2 / 1.1.2 and
the corrected local packages have not been published to GitHub. Peer
discovery, block/transaction propagation and synchronization are built into the
node. A separate networking application is not required. P2P 0.3.0 has separate Full and Light trading editions. Funding requires a
current synchronized SUMUWW node and conditional-spend activation at height 9100.
Full also requires synchronized unpruned Bitcoin Core with txindex; Light does not.
Read the [Bitcoin setup and block-9100 guide](../P2P/Source/BITCOIN_SETUP.md).
An order or reservation does not transfer funds. See the
[edition comparison and verification limits](../P2P/Source/EDITIONS.md).

English is the first-launch default. All 34 offline UI languages remain
selectable. Existing branding is retained. Text translation does not alter keys,
addresses, amounts or protocol data. This update adds no node enrollment fee.

## Upgrade before block 9,000

The current rules apply at height **9,000 inclusive**. Blocks produced by legacy
software under the old rules at height 9,000 or above are rejected by upgraded
nodes and cannot extend the upgraded chain. Update miners and validating nodes.
Valid legacy blocks through **8,999 remain usable**, including the valid prefix
of a mixed synchronization batch. Wallet keys, valid coins, issuance and halvings
are preserved. Validation follows block rules, not an advertised version string.

## Current consensus behavior

SHA-256d PoW and valid cumulative work remain primary. From height 9000 each
block requires a producer-key commitment. After PoW, a random event has a 20%
probability of starting an asynchronous connection-proof request. Three distinct
witnesses each provide one signature divided into two halves. The two compressed
groups are bound to an exact adjacent parent/child pair and retained with proof
metadata for later verification, including by newly synchronized nodes.

Completed signatures are not a prerequisite for mining or accepting an otherwise
valid block. Missing responses can leave a proof incomplete. Recovery runs
asynchronously. Verified complete proofs participate in equal-work chain choice;
they do not override greater valid work or establish irreversible finality.
New jobs probe the full dynamically discovered candidate inventory through relays and select from the responsive identities, not a fixed ten-node list or just direct peers. Complete discovery of every Internet node cannot be
guaranteed, and one operator may run multiple identities.

Original issuance and halving rules are unchanged. DGW observes 24 preceding
blocks and recalculates every ten blocks from 9000 (9000, 9010, ...); intervening
blocks retain the last required target. The exact-template HTLC spending rule
activates at 9100. Installing P2P does not activate real-money swaps.

## Installation and existing wallets

Extract each complete Windows ZIP before running its EXE. Ordinary wallets
validate and store the blockchain locally; they are not SPV/light wallets.
They need reachable compatible peers and synchronization before balances and
confirmations can be considered current. Windows ordinary wallet data is separate
at `%LOCALAPPDATA%/SUMUWW/Wallet-PC`; the full node can run alongside it.

Android Wallet 1.1.2 has application ID `org.sumuww.wallet.current` and the label
**SUMUWW Wallet Current**. It retains the Wallet Current 1.1.0 signing key for in-place updates and installs alongside
the old `org.sumuww.wallet` app. It cannot overwrite that differently signed app.
Do not uninstall the old wallet or clear its data to install this release.
Export an encrypted backup from the old app and import it into the new wallet,
or use its recovery words if available. Preserve the backup and password. Restore
the same key material to retain the address and ownership of valid coins; chain
synchronization restores the displayed transaction history. A new empty wallet
has a different address. The old wallet binary is not reinstated for post-9000 use.

Public Android signing certificate SHA-256:
`e6b41f98b4c965a76072277b8ea258553901bd7f9fd9b1c3120b567e6212e80a`.
Private signing material is not distributed. Windows EXEs are not publisher
code-signed. Compare the supplied SHA256SUMS.txt before installation.

Explorer reads a node database in read-only mode and maintains its own index.
Run `start-explorer.cmd`; use `--database "C:\path\to\node.sqlite"` to choose
another source. It does not start or synchronize a node and is not a public hosted
service. Its data reflects that selected node's stored active chain.

## Changes and verification

Windows wallet 1.0.2 and Android Wallet Current 1.1.2 include the latest
verified-contact recovery, retry accounting, slow-public-peer deadlines,
listener discovery, ancestry reuse and cooperative proof-history scheduling.
Consensus, wallet formats and the 34 language catalogs are unchanged.

Dependency declarations and hash locks now match the actual Windows runtime,
including transitive dependencies. Each new build checks those version pins.
Android uses its own ABI-specific dependency versions; those are intentional.
Current guides and local checksums identify the files actually distributed.

See [this repair's verification and limits](LOCAL_REPAIR_VERIFICATION.md).
Earlier UI, device and live-network measurements remain in the historical
[UI and language report](UI_LANGUAGE_VERIFICATION.md) and
[full-node recovery report](PEER_RECOVERY_VERIFICATION_0.57.38_0.6.88.md).
They are not new measurements of the rebuilt wallets. No physical-device
endurance run, public-money transfer or mining test was performed for this repair.

## Sources and references

Implementation, tests, build definitions and licenses are in the repository and
named source ZIPs. The Windows wallet source ZIP preserves `Wallet/Desktop` and
`PC/Source` paths because the wallet shares that core. Android signing uses local
private configuration; source builds cannot reproduce the publisher signature.

[Downloads](https://github.com/jack-cal/SUMUWW/releases) ·
[Whitepaper](https://github.com/jack-cal/SUMUWW/blob/main/Documentation/Whitepaper/WHITEPAPER.md) ·
[Connection-proof specification](https://github.com/jack-cal/SUMUWW/blob/main/Documentation/Whitepaper/CONNECTION_PROOFS_9000.md)
