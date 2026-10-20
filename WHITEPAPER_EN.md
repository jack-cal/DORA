# SUMUWW Whitepaper

<!-- htlc-9100 -->
## HTLC upgrade · 9100

The Windows 0.57.28 / Android 0.6.78 upgrade adds exact-template P2WSH SHA256/preimage/CLTV spending at block 9100. Existing mature coins and ordinary P2WPKH transfers remain usable. The separate random BLS rule remains at 9000. This is an authorization extension, not a general script VM or permission to execute public-money swaps. [Exact rules](HTLC_9100.md).
<!-- /htlc-9100 -->

<!-- boundary-v4-9000 -->
## 2026-10-19 · v4 · 9000 · 10%

From height 9000, only blocks selected with a 10% probability require a BLS certificate and split trace. The trace joins successive selected blocks across ordinary PoW blocks. A missing required certificate or conflict with registered history is rejected; valid transactions spending common-history coins remain usable.

[BOUNDARY_V4](BOUNDARY_V4_EN.md)
<!-- /boundary-v4-9000 -->

## Purpose and scope

SUMUWW is an independent coin with its own genesis block, transaction history, network and UTXO set. It implements SHA-256d proof of work, UTXO accounting, secp256k1 verification of owner signatures, independent node validation of blocks and transactions, and chain selection by valid cumulative work.

This whitepaper and the protocol specification define the issuance schedule, genesis, addresses, communication identifiers and supported transaction formats.

## Issuance

Each of the first 150,000 blocks has a subsidy of 50 SMW. The subsidy then starts at 25 SMW and halves every 210,000 blocks, rounded down to an integer number of smallest units.

| Block height | Block subsidy |
|---|---:|
| 0–149,999 | 50 SMW |
| 150,000–359,999 | 25 SMW |
| 360,000–569,999 | 12.5 SMW |
| 570,000–779,999 | 6.25 SMW |
| 780,000–989,999 | 3.125 SMW |
| 6,660,000–6,869,999 | 0.00000001 SMW |
| H ≥ 6,870,000 | 0 SMW |

```text
0 <= H < 150000: S(H) = 5000000000
H >= 150000:
    k = floor((H - 150000) / 210000)
    if k >= 32: S(H) = 0
    otherwise: S(H) = floor(2500000000 / 2^k)
```

Nominal maximum issuance: **17,999,999.97690000 SMW**.
Maximum excluding the unspendable genesis reward: **17,999,949.97690000 SMW**.

A valid block's coinbase may claim the subsidy for its height plus fees from included transactions. Excess issuance is rejected. Fees transfer existing coins. The issuance rules contain no reserved developer allocation. There is no administrator authority for arbitrary issuance, freezing, confiscation or balance modification. A mining reward can be spent when spending height minus creation height is at least 100.

## Proof of work, difficulty and chain selection

SHA-256d proof of work and valid block contents are required. The target average block interval is 600 seconds. Below height 8,064, the previous 2,016-block adjustment rules remain in force. From height 8,064, DGW v3 recalculates difficulty for every block using the 24 preceding blocks on the same parent branch. Actual block intervals vary.

Its genesis hash is `00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97`. Mining candidates use the nBits required for their parent branch. When accepting completed blocks, validating branches or revalidating stored chains, nodes check both the expected nBits and the proof of work.

Nodes validate transactions and blocks before selecting the chain with the greatest valid cumulative work. Work is calculated from each block's valid difficulty target, rather than accepting a peer's claimed hash speed or work. A greater-work branch causes transaction records and UTXOs to be reconstructed for that branch. Confirmation counts may decrease and transactions may leave the current chain.

## Record order and competing branches before height 9000

The **parent block hash** in a header establishes block order. The block at height 101 names a particular block at height 100 as its parent; the block at height 102 names a particular block at height 101. A computer clock or block timestamp does not determine ordering by itself. A block timestamp must exceed the median of the timestamps of up to 11 preceding blocks on its parent path. A new block more than 7,200 seconds ahead of the receiving node's clock is not accepted immediately and may be checked again later. Retargeting also uses timestamps on the corresponding branch.

Two honest miners working from the same block 100 can produce different **101A and 101B**. Their parent and expected difficulty can match while reward addresses, transaction sets or nonces differ, producing different hashes. If both pass PoW and content validation, they are valid competing branches. This alone does not establish a rule violation by either miner.

| Observed state | This node's choice |
|---|---|
| Accepts 101A first, then receives equal-work 101B | Retains active 101A and stores 101B as another valid branch |
| Another node accepts 101B first | That node may retain 101B while cumulative work is equal |
| Valid 102B extends 101B and makes B's cumulative work greater | Selects the branch through 102B as the active chain |

Keeping the first accepted branch during a work tie depends on **each node's reception order**. It does not measure which block was completed first worldwide or make that block the permanent winner. Greater valid cumulative work can later change the choice. Equal-height branches with different difficulties are compared by work, not height alone.

If 101A leaves the active chain, its reward is absent from the current active UTXO set. Ordinary transactions are rechecked against the new chain. Transactions still valid may reenter the mempool; those with missing or already spent inputs are rejected. Each node uses these decisions to keep its ledger state internally consistent.

## Modified miners and validity

Faster implementations of the same calculation must still meet expected difficulty and reward rules. PoW checks whether the submitted hash satisfies the required target. It does not require proof of the time spent, equipment used or optimizations applied, so faster valid calculation is allowed. A faster miner may not arbitrarily choose an easier nBits value or claim extra rewards. Rewards from valid optimization can be transferred to ordinary wallets after maturity.

Normal nodes reject arbitrarily reduced difficulty, excess rewards, nonexistent inputs and invalid signatures. Invalid block outputs do not exist in the normal active ledger, and sending them to an ordinary wallet does not make them valid coins. Signatures prove ownership of existing outputs; they do not authorize issuance of valid outputs from invalid ones.

Before height 9000, a rule-compliant private chain with greater cumulative work can change transaction history. At and after 9000, the additional certificate and registered-history rules in BOUNDARY_V4 also apply. Offline creation alone does not make a block invalid; nodes judge it by the same consensus rules. Confirmations do not guarantee irreversible finality. Proof-of-work security depends on honest mining work and independent node validation, and does not guarantee immunity to majority-hashrate attacks.

## Transactions and UTXOs

The ledger records unspent transaction outputs, or UTXOs. Transactions consume existing outputs and create new ones. Nodes check input existence, duplicates, maturity, owner signatures and amount totals to reject double spending and overspending. The basic spending format is native P2WPKH with `SIGHASH_ALL`.

## Transaction confirmations and mining reward maturity

A transaction's confirmation count is its depth in the current active chain. A transaction first included at block height 101 has 1 confirmation when the active chain tip is at height 101, and 2 when the tip reaches height 102. A transaction not yet included is pending with 0 confirmations. If a chain reorganization removes its block, the count and pending state are recalculated for the new chain.

The mining reward **100-block maturity rule** differs from ordinary transaction confirmations in purpose and applicability.

| Output | Conditions for spending |
|---|---|
| Coinbase output (block reward) | Spending block height minus creation block height is at least 100 |
| Output received through an ordinary transaction | Exists in the valid UTXO set or is created by an earlier valid transaction in the same block, remains unspent and satisfies its spending conditions |

A reward created at height 1 can first be spent in a block at height 101. One miner does not need to mine 101 blocks alone; the height belongs to the same active chain extended by all miners.

Transferring a mature reward to another wallet through an ordinary transaction does not start another 100-block wait for the recipient. For example, an ordinary output created at block height 101 may be spent by a later transaction in the same block, or in a block at height 102 or later, if its spending conditions are met.

## Nodes, storage and operation

Each node stores blocks and UTXOs in its own DB and independently checks received data. Blocks and transactions are relayed over IPv4 or IPv6 TCP; reconnecting nodes obtain and validate missing records, then select the valid branch with the greatest cumulative work. When branches have equal work, each node retains its current branch until a valid branch with strictly greater work becomes available.

## Fees and protocol upgrades

Fees equal total inputs minus total outputs. The sender pays the fee in addition to the payment; the recipient receives the full specified amount. Included fees may be claimed by the block miner at the block reward address with the subsidy. There is no developer share, automatic burn or additional issuance. A higher fee can improve the chance of inclusion when blocks are congested, but does not change the target block interval or guarantee faster propagation or confirmation.

Each node still validates independently; neither the author nor an API caller can force upgrades or mint, freeze or rewrite balances. Adoption of changed consensus rules is voluntary and may split the chain. These rules do not cryptographically prevent people from creating a fork. SUMUWW has a decentralized consensus architecture. Its practical decentralization depends on sustained participation by independent node operators and miners.

## Participation and privacy

Anyone may operate a SUMUWW full node, validate the ledger or mine according to the same consensus rules. Participation requires no central admission authority.

P2P peers can observe connection IP addresses. The protocol does not guarantee participant anonymity.

<!-- boundary-detail -->
## Current source policy: random signature blocks from height 9000

This document describes the 2026-10-19 random-10% source revision, based on Windows 0.57.25 / Android 0.6.75. The existing packaged executables and APK still contain the earlier every-block signature policy. This source revision has not been installed on the user's PC or physical phone or published as a release. A separate audit APK is used only in an owned emulator.

From height 9000, each parent/height context selects whether its next block requires BLS signatures with a 10% probability. The input is the network identity, block height and previous block hash, under the `sumuww-random-boundary-block-10pct-v1` domain. The current candidate's nonce and transactions are excluded. Ten percent is an average probability, not a fixed ten-block interval, a preparation deadline or an unbiased randomness guarantee.

Only selected blocks require a complete certificate. The first selected block has `start: null`; each later selected block links to the latest selected ancestor. Ordinary intervening PoW blocks contain neither a certificate nor a split trace. Native PoW/content/transaction checks and the registered-history conflict checks still apply to them. Signatures do not add a PoW work bonus.

The selected team still has three distinct node identities and three distinct observed IP addresses. Discovery and signed replies can be relayed through indirect peers. The responder count and neighbor-observation count are not capped at 1024 and 32. The BLS private signing keys belong to the actual selected nodes; the public block-selection seed is not their private key. The mining service obtains final signatures after valid PoW is found, while the following candidate can be hashed in parallel. Zero signing delay or delivery completed before PoW is not established by this revision.

## Old software, ordinary transfers and joining a branch

| Input received by this source revision | Verification result |
|---|---|
| Unsigned old-software block at a selected height | Reject: complete boundary proof required |
| Unsigned old-software block at an unselected height | Can pass if native rules and registered ancestry also pass |
| Longer branch conflicting with an already registered selected block | Reject: registered connection conflict; claimed extra work does not bypass it |
| Old-wallet transaction spending a mature, valid, unspent common-history output | Verify the owner signature and amounts; can relay and confirm normally |
| Transaction spending a reward existing only on a rejected fork | Reject for a missing/spent input; block-certificate checks are separate from wallet signatures |

Software age alone is not a transaction field or a blanket reason to refuse valid existing coins. A TCP handshake does not establish post-activation block compatibility. A peer that cannot supply the necessary certificate cannot supply that selected block to this revision.

The former every-block-policy database marker can be updated only before any block at or above activation exists, and only when all proof, tail and registration tables are empty. Verified pre-activation blocks, UTXOs, wallets and balances are preserved. A database already using the old policy after activation is refused instead of silently reinterpreting its history.

## Runtime requests, connections and retained addresses

Active discovery objects and their wait events are preserved regardless of how many queries are present. Unowned old-parent queries and idle/finished/cancelled queries are cleaned up. A local discovery with no fresh response ends with an explicit idle error; it does not certify a partial response set or secretly redraw a team.

There is no 512-call limit or default direct-peer count limit, and the address cache has no 128-entry or 64-KiB limit. Failed contacts are removed; healthy alternate connections are protected. Expired retry-suppression entries and completed call records are removed. Local idle retention is `max(60 seconds, socket_timeout * 8, measured_processing_time * 2)`; active send/execution/waiter references are protected. Saved manual preferences remain distinct from the discovery cache. An explicitly supplied CLI `--max-peers` is still an operator option; the application does not set one by default.

Large boundary messages use authenticated `bpart` fragments, with 256-KiB data parts, ordered offsets, a transfer identifier and complete-message digest verification. A whole proof is not limited to 1 MiB. The native `bblock` envelope still uses a uint32 proof-length field, and normal frame/transaction/block limits, DHT round budgets and per-peer traffic quotas remain separate. The observed test sizes are test inputs, not new count limits.

## Verification evidence and scope

The old 0.57.22 core actually mined and accepted an isolated regtest history through height 8999 and unsigned branches through 9111. The last packaged policy rejected its unsigned block 9000. This revision accepted native blocks 9000–9003 on the tested main branch and rejected selected block 9004 without its certificate. The identical block passed with three real private-key BLS signatures. A conflicting private branch and its reward transfer were rejected; an old common-history transaction was accepted and confirmed. Actual TCP tests also rejected the old peer's unsupported selected block. Selection heights vary with the parent hash.

These are isolated native-code/loopback tests at real numeric heights, not a public-network activation, a worldwide census, independent operator proof or a complete 51% defense proof. The original PoW, genesis, issuance, spending signatures and reward maturity rules remain applicable.

<!-- /boundary-detail -->
