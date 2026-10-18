# SUMUWW Whitepaper

<!-- boundary-v4-9000 -->
## v4 / height 9000 — implementation update

The general PoW branch examples below describe the rules before height 9000. From height 9000, compatible software also requires a complete boundary certificate; from 9001 it verifies the split connection to the signed parent. Three distinct node identities with three distinct observed IP addresses sign, and their BLS signatures are aggregated. Signatures do not add PoW weight. A candidate conflicting with this node’s registered connections is rejected. Discovery does not prove that every worldwide live node was included, and complete protection against 51% attacks has not been established. The detailed implementation, replacement rules, persistence and compatibility requirements are documented in BOUNDARY_V4.

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
## Activation and compatibility

On the public `sumuww` profile the first height requiring a boundary certificate is **9000**. Heights below 9000 retain the previous block-validation rules. Height 9000 requires its own complete certificate, with `start: null`; it does not invent a certificate for block 8999. From 9001 onward, a block also requires the split connection to its certified parent.

Genesis, existing addresses, wallet ownership, UTXOs, subsidies and transaction fees are unchanged. This is an additional consensus validation requirement. Old software does not enforce it; connecting to an older peer before activation does not demonstrate compatibility after activation. Participants need compatible software for the same post-9000 chain. Isolated regtest activation heights used in tests are not public activation settings.

## PoW and the certificate

The block identifier and PoW remain SHA-256d of the original 80-byte header. Boundary proof data is carried separately. It is not inserted into the hash that it signs, avoiding a circular reference. Signatures bind the actual completed block hash, network context, parent connection and election bundle. Transaction contents and nonce therefore cannot be changed while retaining the same certificate.

After finding valid PoW the mining service collects the selected nodes' final signatures, validates the resulting certificate and only then accepts and broadcasts the signed block. While that certificate completes, a worker can hash the next candidate on the staged parent. This implementation can wait for discovery or signatures. It does **not** establish zero delay, a fixed sub-second completion time, or permission to accept an unsigned activated block.

Work is `floor(2^256 / (target + 1))`, accumulated over valid ancestors. Signatures do not add a work bonus. Selection by greatest valid cumulative work applies subject to the boundary validity and already-registered-connection checks below.

## Responders, seed and random selection

Signed queries and responses propagate over authenticated v4 peer sessions and can reach indirect peers. A stored address, a previous connection or a peer counter alone does not make a node an eligible responder. Each response binds its identity, query, ECVRF ticket, current neighbor observations and observed socket IP addresses.

The draw input contains the network identity, parent height and hash, and child height. ECVRF-EDWARDS25519-SHA512-TAI tickets are verified against that input. Ticket outputs and node IDs determine a reproducible draw over the included response bundle. The chosen team contains **three distinct node identities and three distinct observed IP addresses**. This implementation does not determine countries, geographic regions, carriers or human ownership. Several addresses for one identity do not create extra members of the same team.

The bundle must contain a connected graph of mutually reported neighbors and usable IP observations. The current limit is 1024 responses, with at most 32 neighbor observations in each response. Discovery returns when a valid connected response bundle is available. There is **no implemented proof that this bundle contains every live node in the entire worldwide network**. A validated IP observation is a signed neighbor report; other nodes do not independently repeat every remote socket observation.

## Missing replies and replacement

The runtime requests signatures from the missing team members. On a missing or unusable reply it obtains fresh signed readiness replies from other responders and randomly replaces the missing slot among eligible ready identities with a compatible distinct-IP assignment. Completed signatures are retained. There is no approval vote by the two other selected members and no fixed list of standby identities.

The request budget is derived from locally measured processing costs and the response component size; it is not a network-wide consensus deadline. Replacement events identify the requester, block, bundle, slot, displaced identity and reported cause. Receivers verify the signed event and replay the replacement calculation. This authenticates what the requester reported; it does **not** independently prove that a remote node was globally unresponsive. If no replacement is available the runtime keeps the candidate and retries the missing signer.

## Completed signature, split and next boundary

Node identity messages use Ed25519. Boundary signatures use BLS12-381 with proof of possession and three distinct signing keys. The three final signatures on their context-bound messages are aggregated into one 96-byte BLS signature and verified with `AggregateVerify`. This is aggregation, not a shared 2-of-3 private key.

For the next parent-child connection, the **already completed aggregate signature** is split in the BLS group: choose a random nonzero group point A and set B = S − A. Both encoded parts are 96 bytes. Verification checks valid subgroup points and A + B = S, together with the parent block and certificate hashes. The parts are not two independently created signatures, a private-key split, a future-block prediction or smaller total storage than S.

The chain database stores part A in the parent's connection-tail record and part B in the child's proof record, atomically with the accepted block. A later read reconstructs the complete envelope. This is a side record in the chain database; the implementation does **not** rewrite the already-mined parent's 80-byte header or prove that A was included in that header before it was mined.

The child signs a context containing this connection. Its own completed aggregate can then be split for the next child. Validation checks the certificate, parent link, split reconstruction, team selection and replacement transcript before registration. Restart validation checks stored certificates and their connections again.

## Registered history and security scope

From activation, the node stores a height/hash/parent/certificate identity for each accepted boundary. A later candidate conflicting with this node's registered connection, or truncating its registered descendants, is rejected even if it claims greater work. Candidate validation is repeated immediately before signing; local persistent signing locks prevent signing different messages for the same network/height/parent context. Incomplete candidates are persisted and resumed after interruption.

These checks protect a node's registered history. They do not by themselves prove that all independent nodes initially registered the same history. The supplied code has no separate global finality vote resolving independently different initial registrations. Distinct IPs do not prove independent operators; signed observations do not remove Sybil, routing or network-partition risks. Consequently a general or complete 51% attack-prevention guarantee has not been established.

<!-- /boundary-detail -->
