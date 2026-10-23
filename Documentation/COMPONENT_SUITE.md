# SUMUWW component suite — 2026-10-23

| Application | Version | Purpose |
|---|---|---|
| Windows full node | 0.57.38 | Validation, synchronization, wallet and optional mining |
| Android full node | 0.6.88 | Validation, synchronization, wallet and optional mining |
| Windows ordinary wallet | 1.0.1 | Receiving, sending, backup, recovery and activity |
| Android ordinary wallet | 1.1.1 | Receiving, sending, backup, recovery and activity |
| Explorer | 0.4.6 | Read-only local blockchain inspection |
| P2P Full | 0.3.0 | SMW/BTC board and settlement using local full nodes |
| P2P Light | 0.3.0 | SMW/BTC board and settlement using Bitcoin SPV |

The full nodes are the existing published versions, included unchanged. Peer
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
Selection uses the dynamically discovered candidate pool, not a fixed ten-node
list or just direct peers. Complete discovery of every Internet node cannot be
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

Android Wallet 1.1.1 has application ID `org.sumuww.wallet.current` and the label
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

This patch corrects wallet locking and synchronization status, multilingual button
layouts, translation errors and stale verification statements. It retains the
existing consensus implementation. See the [UI and language verification report](https://github.com/jack-cal/SUMUWW/blob/main/Documentation/UI_LANGUAGE_VERIFICATION.md)
for measured results and their limits, including physical Android testing.

Windows wallet: nine native regression tests and 204 measured layouts passed.
Current P2P 0.3.0: 121 regression executions, 4 final UI/recovery executions,
136 layout checks and both frozen 34-language checks passed. Full/Light combinations
completed test-chain trades and refunds. Public Bitcoin header/proof checks were
read-only. See [P2P verification](../P2P/Source/VERIFICATION.txt).
Explorer: 150 Python executions (including inherited repetitions), 43 JavaScript
UI tests and a packaged browser check across 34 languages passed. Android: four
JVM tests passed, including 204 button-caption layouts; corrected app logic also
passed physical-device navigation and disposable-wallet checks on a Samsung
SM-S928N. Live ordinary-wallet synchronization reached height 8949 with three peers.
The final Android version bump is metadata only; see the report for the exact
relationship between physical-device tests and the rebuilt release APK.

Earlier protocol and eight-process isolated-network results remain recorded in
the protocol verification reports. This UI patch does not claim a new public
activation, an independent security audit, Internet-scale discovery or irreversible
finality. P2P funding is gated at height 9100; no public-money settlement was
performed in the verification described here.

## Sources and references

Implementation, tests, build definitions and licenses are in the repository and
named source ZIPs. The Windows wallet source ZIP preserves `Wallet/Desktop` and
`PC/Source` paths because the wallet shares that core. Android signing uses local
private configuration; source builds cannot reproduce the publisher signature.

[Downloads](https://github.com/jack-cal/SUMUWW/releases) ·
[Whitepaper](https://github.com/jack-cal/SUMUWW/blob/main/Documentation/Whitepaper/WHITEPAPER.md) ·
[Connection-proof specification](https://github.com/jack-cal/SUMUWW/blob/main/Documentation/Whitepaper/CONNECTION_PROOFS_9000.md)
