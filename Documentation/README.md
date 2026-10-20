# SUMUWW — Unified Guide and Protocol Reference

Current application versions: Windows node **0.57.28**, Android node **0.6.78**, standalone Android Wallet **1.0.9**, Explorer **0.4.4**, P2P **0.1.7**.

[Components and downloads](../README.md) · [PC history](../PC/README.md#version-history) · [Android history](../Android/README.md#version-history) · [Wallet history](../Wallet/README.md#version-history) · [Explorer history](../Explorer/README.md#version-history) · [P2P history](../P2P/README.md#version-history)

This is the current consolidated documentation. Historical releases retain the documentation and files that accompanied those versions.

## Contents

- [Applications, installation and languages](#applications-installation-and-languages)
- [Whitepaper](#whitepaper)
- [Protocol specification](#protocol-specification)
- [Block-signature linkage — v4 / 9000](#block-signature-linkage--v4--9000)
- [Conditional spending — 9100](#conditional-spending--9100)
- [TCP network protocol](#tcp-network-protocol)
- [Explorer operation](#explorer-operation)
- [P2P operation](#p2p-operation)
- [Source, builds and verification](#source-builds-and-verification)

## Applications, installation and languages

| Application | Purpose | Installation and retained data |
|---|---|---|
| Windows node 0.57.28 | Full node, wallet and mining | Close the app and replace the complete extracted bundle. Preserve encrypted wallets, node database and boundary signing state. |
| Android node 0.6.78 | Full node, wallet and CPU mining | Install the signed APK over the existing app. Do not uninstall or clear data. |
| Android Wallet 1.0.9 | Standalone wallet, receiving, sending and connection settings | Install over the existing `org.sumuww.wallet` app, preserving its encrypted wallet. It is a separate application from the mining node. |
| Explorer 0.4.4 | Read-only local blockchain explorer | Extract the Windows ZIP and run `start-explorer.cmd` or the EXE. Uses a browser on localhost and a separate search index. |
| P2P 0.1.7 | Direct order sharing, wallet-address queries and isolated regtest swaps | Extract all files and run the windowed EXE. Preserve `%LOCALAPPDATA%\SUMUWW\P2P`. Public-money swap execution remains disabled. |

First launch defaults to English. The language selector supports 34 bundled languages; an explicit saved choice is restored. Text catalogs are offline: using the selector does not send wallet data or interface text to a translation service. Arabic/Urdu layouts and traditional Mongolian typography are handled in the corresponding application UI. Amounts, addresses, transaction IDs and protocol values are not translated. A language change does not change the blockchain, wallet keys or signing rules.

Windows and Android node updates use separate release pages selected by `updates.json`. Updates are downloaded and installed manually. Component version numbers are independent. Named source ZIPs include implementation and tests; GitHub's automatic source archives contain this documentation repository.

## Whitepaper

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

## Protocol specification

## 1. Basic principles

- No administrator authority for arbitrary issuance, freezing, confiscation or balance modification.
- Rule-compliant rewards start with the first ordinary block, with no reserved developer allocation in the issuance rules.
- Every node independently validates received transactions and blocks.
- Amounts use integer smallest units; fees transfer existing value.
- Select the branch with the greatest valid cumulative work.
- Preserve history and validate it on restart to restore the same UTXOs.

## 2. Issuance rules

First 150,000 blocks: 50 SMW. Then 25 SMW, halved every 210,000 blocks using integer smallest units.

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


## 3. Genesis and network identity

SUMUWW's basic execution network is `sumuww`, profile `dora-independent-v0.12-p2wpkh`. Genesis is fixed to hash `00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97`, UTC 2026-10-03 00:00:00 and nonce `5129435`. It has only an OP_RETURN output and is not connected to the UTXO set. Initial nBits is `0x1e0377ae`, powLimit is `floor((2^256-1)/4838400)`, address HRP is `sumuww`, and wire magic is `d052470c`. Before height 8,064, the Chain uses 600 seconds, 2,016 blocks, 1,209,600 seconds and a 4-times clamp. The [complete genesis record](sumuww_genesis.json) is included.

Genesis is the fixed height-0 anchor with a previous hash of 0. Full bytes, Merkle root, header hash and PoW are recalculated. Its transaction is not connected to UTXOs. Ordinary coinbase outputs require spending height minus creation height to be at least 100.

SHA-256d proof of work and valid block contents are required. The target average block interval is 600 seconds. Below height 8,064, the previous 2,016-block adjustment rules remain in force. From height 8,064, DGW v3 recalculates difficulty for every block using the 24 preceding blocks on the same parent branch. Actual block intervals vary.

## 4. Blocks, transactions and UTXOs

A block header contains 80 bytes in this order: signed int32 version, previous hash 32 bytes, Merkle root 32 bytes, uint32 timestamp, uint32 nBits and uint32 nonce. Integers are little-endian, and the header ID is SHA-256d. Display hashes are reversed hexadecimal representations of internal raw bytes.

Transactions contain uint32 version, inputs, outputs and uint32 locktime using canonical CompactSize. Inputs record previous txid/index, scriptSig and sequence; outputs record signed int64 smallest-unit amounts and scriptPubKey. Witness serialization uses marker 0, flag 1 and a stack per input. TXID is SHA-256d of non-witness serialization; WTXID is SHA-256d of serialization including witness.

Validation rejects empty inputs/outputs, duplicate inputs, missing or spent UTXOs, invalid signatures, immature coinbase, negative or excessive amounts and output totals greater than inputs. Fees equal input totals minus output totals. Live outputs cannot be overwritten by the same txid/index.

Only the first transaction may be coinbase. Coinbase null outpoint, scriptSig length 2~100 bytes and height prefix are checked. Output total cannot exceed the height's subsidy plus block fees. Merkle mutation and witness commitment are checked. Block weight is `3*base_size + total_size <= 4000000`; sigops cost must not exceed 80,000.

Before block 9100, spending validation supports **native P2WPKH / SIGHASH_ALL** using secp256k1 ECDSA. From block 9100, upgraded nodes additionally validate the exact HTLC template described above. Other spending scripts or signature flags remain unsupported; a general script VM is not implemented. Activation is evaluated at the block spending an output, not the block that created its coins.

## 5. Proof of work, difficulty and time

The SHA-256d digest interpreted as a little-endian integer must be at most the target. Negative, 0, 256-bit-overflow and above-powLimit compact targets are rejected. Raw candidate nBits must exactly match the value expected from its parent and height.

**H < 8,064:** Public operation targets 600 seconds, retargeting every 2,016 blocks over 1,209,600 seconds. At retarget height h, timestamps h-1 and h-2,016 **on the same branch** are used. The first boundary at height 2,016 references heights 2,015 and 0.

```text
# H < 8064
bounded = clamp(time[h-1] - time[h-2016], 302400, 4838400)
new_target = min(floor(old_target * bounded / 1209600), powLimit)
expected_bits = compact_encode(new_target)
```

**H < 8,064:** Only public-style profiles satisfying `powLimit * 4838400 <= 2^256-1` are accepted, matching the comparison implementation's 256-bit intermediate arithmetic. Other heights retain parent nBits; delayed blocks have no arbitrary minimum-difficulty exception.

SHA-256d proof of work and valid block contents are required. The target average block interval is 600 seconds. Below height 8,064, the previous 2,016-block adjustment rules remain in force. From height 8,064, DGW v3 recalculates difficulty for every block using the 24 preceding blocks on the same parent branch. Actual block intervals vary.

```text
H >= 8064:
    T[0..23] = targets of 24 preceding blocks, newest first
    time[0..23] = timestamps of those same blocks
    A = T[0]
    for n = 2..24:
        A = floor((A * n + T[n-1]) / (n + 1))
    elapsed = clamp(time[0] - time[23], 4800, 43200)
    expected_bits = compact_encode(max(1, min(floor(A * elapsed / 14400), powLimit)))
```

A new block timestamp must exceed the median of up to 11 ancestors starting from its parent. Blocks more than 7,200 seconds ahead of the node clock are temporarily inadmissible, not permanently marked invalid. Absolute transaction locktime and relative sequence conditions are checked. General script execution and CSV opcodes remain outside the spending scope. From height 9100, CLTV is supported only within the exact conditional-spend template described in HTLC_9100.md.

## 6. Chain selection, storage and transaction relay

Block work for valid target T is `floor(2^256/(T+1))`, accumulated onto parent work. Among branches that satisfy native rules and the activated certificate/registered-history rules, greater valid cumulative work governs branch selection. Ties retain the current locally accepted branch. This does not establish global convergence of conflicting registered histories.

Nodes exchange version/verack, locator/headers, inventory/getdata and block/transaction messages over TCP. Each uses a separate DB and independently validates received data.

[TCP network protocol](#tcp-network-protocol)

## 7. Address encoding

SUMUWW addresses use Bech32 with HRP `sumuww`, witness version 0, with a 20-byte program for native P2WPKH or a 32-byte program for P2WSH. Consensus spending support for the exact P2WSH HTLC template begins at block 9100. Validation checks the network prefix, checksum and padding. Other-network addresses, mixed case and invalid padding are rejected.

## Block-signature linkage — v4 / 9000

Implementation reference: Windows 0.57.28 / Android 0.6.78, retaining the random-10% v4 policy. This describes the supplied code, not a claim of completed public-network activation or an independent security audit.

## Activation and compatibility

From height 9000, only blocks selected with 10% probability require a complete certificate and split trace. The first selected block has `start: null`; later selected blocks link to the latest selected ancestor, with ordinary PoW blocks allowed between them.

Genesis, existing addresses, wallet ownership, UTXOs, subsidies and transaction fees are unchanged. This is an additional consensus validation requirement. Old software does not enforce it; connecting to an older peer before activation does not demonstrate compatibility after activation. Participants need compatible software for the same post-9000 chain. Isolated regtest activation heights used in tests are not public activation settings.

## PoW and the certificate

The block identifier and PoW remain SHA-256d of the original 80-byte header. Boundary proof data is carried separately. It is not inserted into the hash that it signs, avoiding a circular reference. Signatures bind the actual completed block hash, network context, parent connection and election bundle. Transaction contents and nonce therefore cannot be changed while retaining the same certificate.

After finding valid PoW the mining service collects the selected nodes' final signatures, validates the resulting certificate and only then accepts and broadcasts the signed block. While that certificate completes, a worker can hash the next candidate on the staged parent. This implementation can wait for discovery or signatures. It does **not** establish zero delay, a fixed sub-second completion time, or permission to accept an unsigned activated block.

Work is `floor(2^256 / (target + 1))`, accumulated over valid ancestors. Signatures do not add a work bonus. Selection by greatest valid cumulative work applies subject to the boundary validity and already-registered-connection checks below.

## Responders, seed and random selection

Signed queries and responses propagate over authenticated v4 peer sessions and can reach indirect peers. A stored address, a previous connection or a peer counter alone does not make a node an eligible responder. Each response binds its identity, query, ECVRF ticket, current neighbor observations and observed socket IP addresses.

The draw input contains the network identity, parent height and hash, and child height. ECVRF-EDWARDS25519-SHA512-TAI tickets are verified against that input. Ticket outputs and node IDs determine a reproducible draw over the included response bundle. The chosen team contains **three distinct node identities and three distinct observed IP addresses**. This implementation does not determine countries, geographic regions, carriers or human ownership. Several addresses for one identity do not create extra members of the same team.

The bundle must contain a connected graph of mutually reported neighbors and usable IP observations. There is no fixed responder-count or neighbor-observation-count limit. Discovery returns when a valid connected response bundle is available. There is **no implemented proof that this bundle contains every live node in the entire worldwide network**. A validated IP observation is a signed neighbor report; other nodes do not independently repeat every remote socket observation.

## Missing replies and replacement

The runtime requests signatures from the missing team members. On a missing or unusable reply it obtains fresh signed readiness replies from other responders and randomly replaces the missing slot among eligible ready identities with a compatible distinct-IP assignment. Completed signatures are retained. There is no approval vote by the two other selected members and no fixed list of standby identities.

The request budget is derived from locally measured processing costs and the response component size; it is not a network-wide consensus deadline. Replacement events identify the requester, block, bundle, slot, displaced identity and reported cause. Receivers verify the signed event and replay the replacement calculation. This authenticates what the requester reported; it does **not** independently prove that a remote node was globally unresponsive. If no replacement is available the runtime keeps the candidate and retries the missing signer.

## Completed signature, split and next boundary

Node identity messages use Ed25519. Boundary signatures use BLS12-381 with proof of possession and three distinct signing keys. The three final signatures on their context-bound messages are aggregated into one 96-byte BLS signature and verified with `AggregateVerify`. This is aggregation, not a shared 2-of-3 private key.

For the next connection between selected blocks, the **already completed aggregate signature** is split in the BLS group: choose a random nonzero group point A and set B = S − A. Both encoded parts are 96 bytes. Verification checks valid subgroup points and A + B = S, together with the parent block and certificate hashes. The parts are not two independently created signatures, a private-key split, a future-block prediction or smaller total storage than S.

The chain database stores part A in the parent's connection-tail record and part B in the child's proof record, atomically with the accepted block. A later read reconstructs the complete envelope. This is a side record in the chain database; the implementation does **not** rewrite the already-mined parent's 80-byte header or prove that A was included in that header before it was mined.

The child signs a context containing this connection. Its own completed aggregate can then be split for the next child. Validation checks the certificate, parent link, split reconstruction, team selection and replacement transcript before registration. Restart validation checks stored certificates and their connections again.

## Registered history and security scope

From activation, the node stores a height/hash/parent/certificate identity for each accepted boundary. A later candidate conflicting with this node's registered connection, or truncating its registered descendants, is rejected even if it claims greater work. Candidate validation is repeated immediately before signing; local persistent signing locks prevent signing different messages for the same network/height/parent context. Incomplete candidates are persisted and resumed after interruption.

These checks protect a node's registered history. They do not by themselves prove that all independent nodes initially registered the same history. The supplied code has no separate global finality vote resolving independently different initial registrations. Distinct IPs do not prove independent operators; signed observations do not remove Sybil, routing or network-partition risks. Consequently a general or complete 51% attack-prevention guarantee has not been established.

## v4 transport

The existing 24-byte frame header, network magic, genesis/profile checks and `version` / `verack` handshake remain. Protocol values 1, 2, 3 and 4 are recognized. Discovery address exchange is available from v2; numeric IPv6 address hints from v3, including v4. The boundary-capable runtime first attempts v4 and has compatibility retry paths for older peers.

| Command | Purpose |
|---|---|
| `bhello` | Signed identity / BLS member binding to this socket's exchanged handshake nonces and network |
| `bquery` | Relay the signed parent-context discovery query |
| `bresponse` | Relay a query-bound signed responder record |
| `bcall` | Relay authenticated `ready` / `sign` calls and replies |
| `bpart` | Authenticated multipart transfer |
| `bblock` | Carry a native block with its complete boundary envelope |

Boundary commands require authenticated v4 sessions. Large messages use ordered authenticated `bpart` fragments with 256-KiB data pieces and a complete-message digest. Whole proofs are not capped at 1 MiB. The `bblock` logical payload remains `uint32_le proof_length || canonical_JSON_proof || serialized_native_block`. Normal frame/block/transaction limits and per-peer traffic quotas remain separate.

## Source locations and operational checks

Implementation: `sumuww/boundary.py`, `boundary_crypto.py`, `boundary_runtime.py`, `boundary_state.py`, `chain.py`, `app_service.py`, `peer.py` and `wire.py`; Android bundles the same consensus modules. Separate boundary node keys are unrelated to wallet spending keys and must be retained with node state for safe signing continuity. Protect backups containing those private node keys.

Operators should check the installed version, selected public profile, activation height, actual authenticated peer sessions and boundary errors. A connected peer is not evidence that it is mining. A block's acceptance, chainwork and certificate validation are separate from saved addresses and discovery responses. Project-run isolated tests and device UI checks do not establish worldwide adoption or public-chain activation.

### Current compatibility and request handling

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

## Conditional spending — 9100

This upgrade extends transaction authorization, independently of the
existing BLS activation at 9000. Native P2WPKH transfers remain valid before
and after 9100. The age of the spent coins is not a restriction; coinbase
maturity and ordinary value/signature rules still apply.

The newly supported P2WSH template is:
`IF SHA256 <32-byte hash> EQUALVERIFY <receiver pubkey> CHECKSIG ELSE
<refund height> CHECKLOCKTIMEVERIFY DROP <refund pubkey> CHECKSIG ENDIF`.
Only canonical compressed keys, exact pushes, 32-byte preimages and SIGHASH_ALL
are supported for this new template. Existing P2WPKH consensus is unchanged.
Refund height is enforced by transaction finality and a nonfinal input sequence.

The rule is evaluated at the candidate block height, including mempool admission
for tip+1. It does not retrospectively reinterpret blocks below 9100. Public
nodes use the fixed activation 9100; isolated regtest tests must opt in.
The separate BLS policy remains fixed at 9000 and random 10% selection.

`gethtlcinfo` reports the configured height and current/next block activation.
`gettxout` and `findspendingtransaction` expose actual locally validated chain
observations; peer completion messages do not replace those observations.

Public-money exchange execution remains separately disabled in SUMUWW P2P.

## TCP network protocol

<!-- boundary-v4-9000 -->
## 2026-10-19 · v4 · 9000 · 10%

From height 9000, only blocks selected with a 10% probability require a BLS certificate and split trace. The trace joins successive selected blocks across ordinary PoW blocks. A missing required certificate or conflict with registered history is rejected; valid transactions spending common-history coins remain usable.

[Block-signature linkage](#block-signature-linkage--v4--9000)
<!-- /boundary-v4-9000 -->

## Frames and resource limits

Each frame consists of a 24-byte header and payload. Integer fields are little-endian; hashes use the internal raw 32-byte order. The length is checked before reading the payload, then the checksum is validated.

| Field | Bytes | Local rule |
|---|---:|---|
| Magic | 4 | Selected network's magic: sumuww `d052470c`, regtest `d0524709`, lab `d052470b` |
| Command | 12 | 1~12 English letters/digits starting with a lowercase English letter; remaining bytes are NUL |
| Payload length | 4 | uint32; ordinary commands: 4,000,000 bytes; v4 command-specific limits: see BOUNDARY_V4 |
| Checksum | 4 | First 4 bytes of SHA256d(payload) |

Normal EOF at a frame boundary is distinguished as `PeerDisconnected`. EOF after only part of a header/body, invalid magic/padding/checksum/size, and frame timeout are errors. Whole-frame reading and drain each have a deadline. Command payloads are also checked for canonical CompactSize, lengths, counts, and trailing bytes.

## Handshake and messages

Each frame's magic is compared with the selected network. After both sides send `version`, protocol, genesis, profile, and self-connection nonce are checked. Empty `verack` messages must then be exchanged before ordinary messages are processed. A peer's advertised tip is a discovery hint, not an adopted validated chain state. Claimed height or work never drives chain selection.

| Command | Payload | Handling |
|---|---|---|
| version | uint32 protocol=1/2/3/4, genesis32, uint64 nonce, CompactSize UTF-8 profile 1~64 bytes, tip32 | Exact protocol/genesis/profile comparison |
| verack | Empty payload | Complete handshake |
| getheaders | CompactSize locator count, raw hashes, stop32 | Return after the active chain's common ancestor |
| headers | CompactSize count, each 80-byte Header | Check target within selected PoW limit, PoW, version, and connection order; contextual DAA checked during body validation |
| inv / getdata / notfound | CompactSize count, each uint32 kind+digest32 | kind1=tx, kind2=block; at most 256 |
| block | Canonical block bytes, including witness | Match requested header, then validate branch ancestors' expected nBits and existing Chain conditions |
| tx | Canonical transaction bytes, including witness | Match requested txid, then existing mempool admission |
| ping / pong | uint64 nonce | Check connection responsiveness |
| getaddr | Empty payload | Protocols 2, 3 and 4; bounded request rate |
| addr | listener_present + CompactSize peer_count + endpoints | Protocols 2, 3 and 4; untrusted address hints |

This local `headers` message does not append a transaction-count byte to each header. The version payload and witness inventory handling also differ from Bitcoin wire messages. Commands sharing names does not mean the program can connect to Bitcoin peers.

Inventory kind 1 is the raw 32-byte TXID of the transaction excluding witness; kind 2 is the raw 32-byte SHA256d of the 80-byte block header. `getheaders` returns starting after the first active-chain hash found in locator order. With no common hash, it returns after genesis; a stop of 0 proceeds up to the count limit. When the active-chain stop hash is encountered, that header is included and the response ends.

## Synchronization and transaction relay

A node requests headers using its own validated block locator. Known blocks are skipped and unknown blocks fetched in sequence. The header stage checks the selected profile's PoW limit, PoW, and linkage; it does not require fixed regtest nBits on all networks. At this stage, headers are not stored as validated work or activated as the chain.

Received full blocks can be stored/activated only after consensus validation passes every check: expected nBits calculated from the actual branch's parent/ancestors and timestamps, amounts, maturity, signatures, time, and commitments. Valid blocks crossing lab adjustment boundaries are relayed. Blocks with valid PoW but incorrect contextual nBits are rejected at the body stage. Unvalidated headers or a peer's tip advertisement do not change UTXO or tip in this case.

When a batch ends, the next locator is built from the last validated branch hash. The next page can be fetched even if that branch is shorter than or tied with the current active chain; once its total valid cumulative work grows larger, existing consensus rules select it.

## P2P discovery encoding and compatibility

The new `getaddr` message is empty. The `addr` payload has the following binary layout; integers are little-endian and counts use canonical CompactSize. A listener, if present, is separate from the count of remaining peers.

```text
getaddr: empty
addr:
    uint8 listener_present (0 or 1)
    CompactSize peer_count
    [listener endpoint if listener_present == 1]
    peer_count endpoints
endpoint:
    CompactSize host_byte_length
    host ASCII bytes
    uint16_le port
```

A host contains 1–253 ASCII bytes. DNS names and IPv4 addresses use letters, digits, dots and hyphens. IPv6 addresses use canonical numeric notation; scoped and IPv4-mapped IPv6 addresses are rejected. A port is 1–65535. At most 32 endpoints, including the listener, are allowed; the payload limit is 8259 bytes. Address exchange requires protocol 2, 3 or 4, and IPv6 hints are sent only to protocol 3 or 4 peers.

With the boundary runtime enabled, outgoing discovery connections first try protocol 4. Without that runtime, the discovery baseline first tries protocol 3. A recognized protocol 2 peer can be retried with protocol 2. Listeners initially announce protocol 1 for older clients. After matching network magic, genesis and profile, an eligible protocol 1 peer that closes or resets before acknowledgement permits one retry with protocol 1. Wrong-network peers do not trigger a downgrade. Protocol 1 sessions receive no `getaddr` or `addr` messages. Every successful session requires the final acknowledgement before normal full-node synchronization.

## Explorer operation

```text
SUMUWW Explorer 0.4.4

Windows application ZIP: extract everything and run start-explorer.cmd (or SUMUWW-Explorer.exe).
The launcher opens http://127.0.0.1:8770 in your browser. If an explorer is already
running there, it opens that instance instead of reporting a duplicate-port error.
Double-clicking the packaged EXE also opens the browser. No Python is required.
Use --no-browser to run the EXE without opening a browser.
Source ZIP: requires Python 3.10 or newer. Install PDF dependencies first: python -m pip install -r requirements.txt.
The source launch script can use this workspace's existing Python runtime, or Python on PATH.

Command line:
  python server.py
  python server.py --database "C:\path\to\node.sqlite" --port 8770

Features:
  Block height/hash, transaction ID and SUMUWW address search.
  Active-chain block/transaction details, input/output links, fees and confirmations.
  Address transaction history, confirmed/available/immature balances, and unspent outputs.
  Local mempool, pagination, 34 bundled interface languages, and responsive browser UI.
  Transaction history filters: all, mining rewards, and ordinary transfers.
  Click the total/reward/ordinary counts to open the matching transaction list.
  Address-relative received outputs, spent inputs and net change (including change outputs).
  Last block timestamp, source read time and elapsed block age, shown separately.
  Local difficulty/interval/transaction charts for 24, 144 or 2,016 recent blocks.
  Raw block and transaction binary downloads; Merkle inclusion proof view/download.
  CSV exports for blocks, confirmed address history and the selected statistics sample.
  Periodic refresh every 15 seconds while the page is visible.

Data handling:
  Reads the selected SUMUWW node.sqlite using SQLite mode=ro and query_only.
  Uses a separate data/explorer.sqlite search index. The source database is never written.
  Active-chain reorganizations remove displaced records from the explorer index.
  Wallet files, passwords, keys, peer connections and mining settings are not accessed.
  This explorer does not mine, start a node, sign transactions or broadcast data.
  The node must synchronize independently for its stored blockchain to stay current.
  Block timestamps are shown in the browser's local timezone.
  Available balance uses coinbase maturity at the next block height and excludes
  confirmed outputs spent by transactions in this node's local mempool.
  Pending received outputs are displayed separately, not added to available balance.
  Pending outputs already consumed by another local mempool transaction are excluded.
  Address view lists up to 100 UTXOs; transaction history is paginated.
  Transaction inputs and outputs describe the stored record; the explorer is not
  an independent consensus validator or a global network connectivity monitor.
  Only the selected node's active chain is displayed, not stored side branches.
  The UI retries if the source snapshot changes between the page summary and detail.
  A failed refresh never publishes a partially updated index. Failed reads hide stale UI numbers.
  New block bytes are checked against their indexed hash, parent and transaction Merkle root.
  An unchanged tip avoids scanning/reindexing the full historical chain on every refresh.

Access:
  Listens on 127.0.0.1 only. This URL is available on this PC, not publicly online.
  Public hosting is not configured. Running it does not open firewall ports.
  No cloud services, analytics, CDN scripts or external fonts are used.
  Stop the explorer with Ctrl+C in its console.
  Only one process may own an index. A second instance requires a different --index and --port.
  All downloads are local; no external services are contacted.
  Download controls use the displayed data snapshot. If source data changes, refresh
  the page before retrying a rejected download (snapshot_changed). Unchanged reads
  retain the snapshot identifier. Unknown Merkle-proof formats are rejected.
  CSV buttons export up to 1,000 recent blocks/address transactions; API limit is up to 10,000.
  Address CSV supports offset for further pages. Pending transactions are not included in address CSV.
  Statistics CSV includes the complete selected sample, up to 2,016 blocks.
  Address received/spent totals describe outputs/inputs. Received totals can include change;
  net change is received outputs minus spent inputs, not a separate transfer amount.
  If pending inputs cannot be resolved, spent/net amounts are unknown rather than zero.
  Difficulty charts are relative to SUMUWW's initial target, not Bitcoin difficulty 1.
  Block timestamp differences can be negative; graphs preserve the stored values.
  Merkle proofs establish TXID inclusion in the included header, not finality, proof of work,
  transaction signature validity or witness-data verification.
  Verify a downloaded proof offline without reading a node DB:
    SUMUWW-Explorer.exe --verify-proof "SUMUWW-proof-....json"
  The explorer does not observe peer synchronization, so it does not label stored data as globally current.
  A missing or corrupt source is reported without creating or repairing the source database.
  Unknown/corrupt index files are refused; choose a new --index path to build a fresh index.
  If the default port is busy, close the other explorer or use --port 8771.

Checks:
  python -B -m unittest -v test_explorer.py
  node --test test_ui.cjs
  Tests use isolated synthetic records to exercise indexing, not consensus acceptance.
  UI unit tests use a DOM/fetch fixture; actual browser checks are recorded separately.
  To build an EXE, install PyInstaller in your build environment and run build-windows.cmd.

Source codecs:
  vendor/sumuww contains the minimal block/transaction/address codecs and their
  dependencies copied from SUMUWW Windows source v0.57.20. See vendor/LICENSE.

Language assets:
  33 language options: Korean, English, Japanese, simplified/traditional Chinese
  (Taiwan and Hong Kong), French, Spanish, Portuguese, German, Italian, Russian,
  Arabic, Swahili, Hindi, Indonesian, Vietnamese, Turkish, Thai, Bengali, Urdu,
  Polish, Dutch, Filipino, Tamil, Czech, Danish, Finnish, Greek, Norwegian,
  Swedish, Serbian and Mongolian (Cyrillic). Language choice is saved locally.
  Arabic/Urdu use right-to-left layout. Hashes and chart axes remain left-to-right.
  Additional translations were prepared with Google Translate at build time;
  technical identifiers remain unchanged. Runtime uses bundled static assets.
  Rebuild languages.js offline from included locales: python prepare_languages.py
  The optional --translate-missing flag contacts Google only for missing locale files or keys.

Page navigation: current/total page numbers, clickable first/last/nearby pages, and a direct page-number input. The selected transaction kind is preserved.

Analytics added in 0.4.0:
  Fees: smallest units/vB (100,000,000 units = 1 SMW), ancestor-package rates,
  25th/50th/90th percentile estimates from local pending + up to 200 confirmed
  ordinary transactions. No inclusion time guarantee; zero fees may be valid.
  Missing input amounts are unknown, never fabricated zero fees. Mempool sizes,
  fee buckets, known fee totals and unresolved counts describe this node only.
  Related transactions: direct input parents, spending children, pending ancestor
  and descendant packages. This does not identify owners or verify RBF support.
  Mining: 24/144/2016-block work/time hash-rate estimates, claimed rewards,
  known fees, payout-address distribution, current/next difficulty and changes.
  Payout addresses do not establish miner/pool identity; shares can overlap.
  Block comparison: the explorer observes its source every 3 seconds while running,
  even with its browser closed. It saves a conservative fee-package projection
  before indexing the next block, then compares ordinary TXIDs actually included.
  This is not the miner's template or a consensus/signature/sigops validator.
  Old blocks without a prior observation have no comparison data. Differences
  can reflect timing, local visibility or policy, not misconduct. Reorg cleanup
  removes orphaned observations along with displaced indexed blocks.
  Transaction filters: UTC dates, inclusive height and output-total bounds,
  height/time/amount/fee/rate sorting, ascending or descending. Paging and export
  preserve filters. Output total includes change, not just a payment amount.
  Address period analysis: opening/closing balance, exact received/spent/net,
  balance after each transaction and a chart grouped into up to 512 height buckets.
  Set maximum height to obtain the balance at a past block. Includes immature
  rewards, excludes pending transactions and the unspendable genesis reward.
  Address date filters map to a contiguous height span, because block timestamps
  can move backward; they do not prove a wall-clock balance at that instant.
  PDFs: transaction receipt, filtered transaction report, address period report.
  Each states local chain tip, read time, scope and included/total row counts.
  At most 10,000 rows per report/export. These are local records, not signed
  payment certificates, ownership proofs, legal receipts or finality guarantees.
  PDFs use subset-embedded Windows fonts, without distributing the font files.
  Source on systems lacking these fonts uses English PDF labels as stated in-file.
  New PDF runtime libraries: ReportLab, Pillow, python-bidi, arabic-reshaper,
  uharfbuzz. Their notices are included in THIRD-PARTY-NOTICES.txt.
  Run all isolated reader/analytics tests: python -B -m unittest discover -p "test_*.py"
  PDF tests also need pypdf; it is not required to run the explorer.

Fixes in 0.4.2:
  Include and freeze the DGW module required by mining analysis from height 8064.
  Detect the current SUMUWW data directory and SUMUWW_DATA_DIR, while preserving
  existing DORA data locations and active-node marker compatibility.
  The node, mining process, chain database and wallet settings are not changed.

Verification for 0.4.2:
  83 isolated reader/HTTP/analytics/PDF/path tests and 40 UI-code tests passed.
  Activated-difficulty regression covers actual heights 8063 and 8064.
  62 requests against the exact new EXE on the actual local height-8533 chain
  passed, including raw records, proof verification, 4 PDF languages, CSV,
  address balances against read-only source UTXOs and loopback request rules.
  Browser checks covered searches, copy, pagination, filters, analytics,
  English/Arabic/Korean language changes, address history and actual downloads.
  Original EXE failed with only the new SUMUWW data path; this EXE succeeded.
  Bytecode for server, analytics, reports and DGW matched this source.
  Local mempool was empty; nonempty cases were exercised in isolated tests.

Changes in 0.4.4:
  Display and search witness-v0 32-byte P2WSH output addresses used by HTLCs.
  Repair missing addresses when opening recognized older explorer indexes.
  The address codec and migration are read-only with respect to the node chain.
  Showing an address or a Merkle inclusion proof does not verify the contract's
  spending conditions, a global chain tip or cross-chain completion.

LANGUAGE SETTINGS
First launch defaults to English. Use the language selector for 34 offline catalogs. An explicit browser language choice is retained. Missing/invalid settings fall back to English.
```

## P2P operation

```text
SUMUWW P2P 0.1.7 — Native Windows application

CURRENT FUNCTIONALITY
SMW/BTC orders and signed reservations can be shared directly with another
instance. Existing wallet addresses can be queried through a local node.
Exchange execution is restricted to isolated SUMUWW and Bitcoin Core regtest.
Public-money funding and swaps remain disabled. The separate SUMUWW node
0.57.28 / Android 0.6.78 upgrade adds HTLC validation at height 9100; installing
this P2P application does not activate public trading.

RUNNING ON WINDOWS
Extract the complete Windows ZIP and run SUMUWW-P2P.exe. It opens a native
desktop window without a browser or command prompt. Keep all extracted files
together. Data is stored in %LOCALAPPDATA%\SUMUWW\P2P. Existing orders,
identity and encrypted test-vault files are retained. Closing the window
stops application-owned work and leaves stored records in place.

WALLET ADDRESS QUERIES
In the wallet-query view, select SMW or BTC, enter the local RPC URL, the
matching node authentication-file path and an existing receiving address.
SMW normally uses http://127.0.0.1:18443/rpc with its RPC token file.
Bitcoin Core normally uses http://127.0.0.1:8332/ with its .cookie file.
Use the actual ports and files configured for your local nodes. The app does
not enable RPC or change firewall settings. Authentication is read from the
local file, not embedded in URLs or sent to peers. Queries are manual and
read-only: no wallet unlock, private-key export or transfer is requested.
Bitcoin address queries report the selected P2WPKH address's UTXO balance,
not the sum of an entire wallet. Saved links contain address and file-path
settings. Querying an address does not enable public swaps.

DIRECT PEER CONNECTIONS
Enter the other instance's reachable IPv4/IPv6 address and port in the
connection view. The listener defaults to loopback. External inbound use
requires a reachable bind address, port and suitable network configuration.
There is no automatic Internet discovery, NAT traversal or public relay.
Orders, cancellations and reservations are Ed25519-signed and saved in
SQLite. Order quantities and the total BTC price are chosen by the user.
The operator service fee is 0%; blockchain transaction fees are separate.
Reservation is an agreement record, not a transfer.

ISOLATED TEST VAULT
Create a vault with a password of at least 12 characters and its confirmation.
Different random secp256k1 keys are used for SMW and BTC. The vault uses
AES-256-GCM and scrypt (N=32768, r=8, p=1), with random salt and nonce.
Back up wallet-regtest.vault privately. Both its backup and password are
required for recovery. Existing vaults are not overwritten. Restart locks
the vault; locking prevents new signatures, while previously approved work
can complete. Test addresses use drt for SMW and bcrt for Bitcoin.
These are test addresses, not public-chain deposit instructions.

TWO-PARTY REGTEST EXCHANGE
Each participant holds and signs with their own local test keys; the other
participant's private keys are not imported. Both sides must use compatible
local chain histories and authenticated RPC services. Bitcoin public-network
nodes are rejected for exchange execution. Standard SUMUWW node query and
transaction RPCs are supported alongside the research RPC adapter.
1. Select the same signed reservation, prepare local keys and exchange terms.
2. The SMW seller locks their test asset after preparing a signed refund.
3. The BTC buyer verifies the actual SMW lock before locking their BTC.
4. The seller verifies both actual locks and claims the BTC test output.
5. The buyer extracts and validates the secret from Bitcoin chain data and
   claims the SMW output; a peer completion notice is not sufficient.
6. After the refund height, each owner can broadcast their saved refund
   without the other peer or an unlocked vault, including after restart.
Every spending step requires the local user's action. Remote messages do not
unlock a vault or initiate spending. Retries use the same saved transaction.
Keep refund records and access to nodes that can query/broadcast transactions.

TEST POLICY
One confirmation, a 40-block SMW refund margin, a 15-block BTC margin and
fixed test fees are accelerated-regtest settings, not public-money policy.
Public fee estimation, confirmation/reorg policies and refund timing are
not enabled by this build. This application is not a custodial exchange.
The source ZIP contains implementation, tests and build files. GitHub's
automatic source archives contain the documentation repository instead.
Compare SHA256SUMS.txt with the downloaded files before use.

LANGUAGE SETTINGS
English first-launch default. Select any of 34 bundled languages; the choice is stored locally and restored. Switching language preserves entered quantities, order side, current tab, connection settings and records. Traditional Mongolian captions use the included licensed font.
```

## Source, builds and verification

Implementation sources, tests, dependencies, licenses and build instructions are included in each component's named source ZIP. Compare SHA256SUMS.txt with downloads. Preserve wallet backups privately; never put passwords, seed phrases, private keys or RPC authentication files in public reports.

The language revision was checked with source regression tests, native desktop tests and Android API 35 virtual native-rendering tests. These checks are distinct from a physical phone test or public-network security proof. Consensus activation heights remain 9000 (random BLS policy) and 9100 (exact HTLC template). Public-money swaps remain disabled in the P2P application.
