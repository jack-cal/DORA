# SUMUWW component suite — 2026-10-22

| Application | Version | Purpose |
|---|---|---|
| Windows full node | 0.57.34 | Validation, synchronization, wallet and optional mining |
| Android full node | 0.6.84 | Validation, synchronization, wallet and optional mining |
| Windows ordinary wallet | 1.0.0 | Receiving, sending, backup, recovery and activity |
| Android ordinary wallet | 1.1.0 | Receiving, sending, backup, recovery and activity |
| Explorer | 0.4.5 | Read-only local blockchain inspection |
| P2P | 0.1.8 | Signed order sharing and isolated regtest exchanges |

The full nodes are the existing published versions, included unchanged. Peer
discovery, block/transaction propagation and synchronization are built into the
node. A separate networking application is not required. The P2P application in
this suite is the existing order/exchange program; public-money swaps remain
disabled. An order or reservation does not transfer funds.

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

Android Wallet 1.1.0 has application ID `org.sumuww.wallet.current` and the label
**SUMUWW Wallet Current**. It is signed with a new key and installs alongside
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

The PC wallet adds a native interface without mining controls, explicit payment
review, single-use quotes, automatic locking and encrypted import/export. Android
retains its wallet UI and adopts the current node protocol/runtime. Explorer now
uses the ten-block DGW interval for predicted targets. P2P embeds the current
shared core while retaining its regtest-only swap guard. Obsolete bundled guides
describing the withdrawn boundary-certificate design have been replaced.

Recorded local checks:

- Wallet backend: 10 passed, including encrypted legacy import, unchanged address,
  public key and spendable outputs, real peer transfer in regtest, quote replay
  protection and automatic lock. Originals were not overwritten.
- PC wallet: 3 native Tk tests passed (34-language rendering, create/lock/unlock,
  payment review/cancel/confirm, backup overwrite protection). The frozen EXE
  separately passed create, backup, lock, same-address restore and mining-command
  rejection checks; its actual window was inspected.
- Explorer: 150 unittest executions passed, including inherited repeated cases;
  this is not a claim of 150 distinct tests. The packaged EXE served a read-only
  chain snapshot and the browser interface was inspected.
- P2P: the 81-execution full run had one source-manifest format failure. That
  format was corrected and all 28 executions in the affected module then passed.
  The other 80 executions passed in the full run. The packaged native window ran.
- Protocol: 45 unittest executions passed, including inherited repeated cases,
  with activation-prefix, 20% event, DGW10, transport and recovery checks. The
  actual-height fixture covered the 8999/9000 boundary.
- Eight independent local regtest process identities exercised withholding,
  asynchronous recovery, restart and late-node verification. During an injected
  eight-second witness delay, five easy-target blocks were mined in 0.063 seconds.
  The four final nodes agreed on height 51, tip, UTXO digest and four proofs across
  both beacon generations. This timing is not a mainnet performance estimate.
- Android release and instrumentation APKs built successfully. Three Robolectric
  tests passed, covering 34 language layouts. APK signature and alignment verified.
  No physical Android device was connected for this run; device instrumentation,
  installation and live mobile peer synchronization have not been reverified.

These checks do not establish an independent security audit, Internet-scale
discovery, mainnet endurance or irreversible finality. Real-money P2P swaps remain
disabled. The connection-proof system remains experimental.

## Sources and references

Implementation, tests, build definitions and licenses are in the repository and
named source ZIPs. The Windows wallet source ZIP preserves `Wallet/Desktop` and
`PC/Source` paths because the wallet shares that core. Android signing uses local
private configuration; source builds cannot reproduce the publisher signature.

[Downloads](https://github.com/jack-cal/SUMUWW/releases) ·
[Whitepaper](https://github.com/jack-cal/SUMUWW/blob/main/Documentation/Whitepaper/WHITEPAPER.md) ·
[Connection-proof specification](https://github.com/jack-cal/SUMUWW/blob/main/Documentation/Whitepaper/CONNECTION_PROOFS_9000.md)
