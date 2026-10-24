> Documentation edition 2.2, 24 October 2026, for PC 0.57.40 / Android 0.6.89. Download: https://github.com/jack-cal/SUMUWW/releases/tag/whitepaper-v2.2-en. Existing application release archives remain unchanged.

# SUMUWW Whitepaper

## Purpose and scope

SUMUWW is an independent coin with its own genesis block, transaction history, network and UTXO set. It implements SHA-256d proof of work, UTXO accounting, secp256k1 verification of owner signatures, independent node validation of blocks and transactions, and chain selection by valid cumulative work.

## SUMUWW connection proof

A connection proof records the endorsement of a specific parent block A and its direct child B. After A is mined, A's producer handles the proof in the background once B is known. Requests remain bound to that pair. Block creation, acceptance and propagation do not wait for the proof.

Three selected nodes each sign the same network, A/B hashes, height, witness team and randomness context with Ed25519. Each node splits its 64-byte signature into two 32-byte halves and returns them to A's producer: six pieces in total. The three front halves form a 96-byte bundle for A; the three back halves form another for B. Each bundle is compressed only if it becomes smaller; otherwise it keeps its original encoding.

A's producer signs the paired attachment; B's producer verifies it and signs a receipt binding the same pair. The completed record is stored and relayed. Attachments reference the exact block hashes without rewriting mined block bytes. Reassembly restores three verifiable signatures, not a private key. The proof attests to this signed connection; every block still requires independent consensus validation.

## Random selection and distributed randomness

A verified distributed random value selects a connection event with probability 20%. This is neither a fixed five-block schedule nor a guarantee that 20% of blocks obtain completed proofs. Starting with PC 0.57.40 / Android 0.6.89, a new job probes the producer's entire discovered identity inventory through authenticated relays. It then samples three distinct responding identities without replacement using the verified beacon. Silent contacts remain in discovery for later attempts. A response shows availability at that moment, not a guarantee of a later signature. This is a local availability policy, not consensus membership. Already selected jobs keep their exact A/B pair, beacon and three witnesses. Discovery extends through relays, without a direct-neighbor filter, per-IP quota or fixed candidate count. No admission, exit procedure or participation fee is required; one operator may run multiple nodes.

The random beacon uses Feldman DKG and threshold BLS, with its public setup anchored on chain before A. Enough valid shares reconstruct the same output despite some missing replies. Below the threshold, the proof remains incomplete while mining continues. Initial setup needs all listed dealers' contributions and a readiness quorum. Unavailable beacon groups can be replaced by background fresh-key DKG, with each replacement anchored in PoW and bound to its predecessor and an ancestor round. Old proofs keep their original key; new generations apply only to later source blocks. Recovery needs enough responsive participants and eventual delivery, and never gates mining. This is fresh-key recovery, not recovery of a lost old secret; same-key resharing is not implemented. A worldwide complete candidate census and resistance to a producer's candidate omissions are not established.

## Chain selection and conflicting evidence

Valid cumulative PoW takes priority. From activation, equal-work branches are compared by the number of valid, nonconflicting proven connections on each branch, then by the smaller tip hash in the protocol's internal byte order. Repeated proofs of the same edge count once.

Conflicting connections for the same parent/height position all receive zero weight, even if all three witnesses double-sign. Late proofs or newly revealed conflicts can change an equal-work choice. A valid greater-work branch still wins. Connection evidence does not provide irreversible finality, prevent every fork or guarantee resistance to a majority-hashrate attack.

## Verification by a later node

A later node obtains the blocks, anchored randomness setup, completed paired proofs and relevant conflict evidence from peers. It decodes both bundles, decompressing only those marked as compressed, joins each witness's halves and verifies the three signatures, both producer receipts and the parent-child relationship. Missing or invalid evidence earns no connection weight; it does not by itself invalidate an otherwise valid PoW block. Independent verification requires the supporting records to remain available.

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

## Proof of work and difficulty

The chain uses SHA-256d PoW with a 600-second target interval. Before height 8064, the original 2016-block adjustment applies. From 8064 through 8999, DGW v3 recalculates every block using the preceding 24 blocks on that branch. From 9000 it recalculates at 9000, 9010, 9020… using the same 24-block algorithm; intervening blocks retain their parent's difficulty. Nodes check the required target as well as the hash. Connection evidence adds no PoW work.

## Transactions and UTXOs

The ledger records unspent transaction outputs, or UTXOs. Transactions consume existing outputs and create new ones. Nodes check input existence, duplicates, maturity, owner signatures and amount totals to reject double spending and overspending. The basic spending format is native P2WPKH with `SIGHASH_ALL`.

## Fees and protocol upgrades

Fees equal total inputs minus total outputs. The sender pays the fee in addition to the payment; the recipient receives the full specified amount. Included fees may be claimed by the block miner at the block reward address with the subsidy. There is no developer share, automatic burn or additional issuance. A higher fee can improve the chance of inclusion when blocks are congested, but does not change the target block interval or guarantee faster propagation or confirmation.

Each node still validates independently; neither the author nor an API caller can force upgrades or mint, freeze or rewrite balances. Adoption of changed consensus rules is voluntary and may split the chain. These rules do not cryptographically prevent people from creating a fork. SUMUWW has a decentralized consensus architecture. Its practical decentralization depends on sustained participation by independent node operators and miners.

## Activation and compatibility

Valid history through 8999 remains usable even when transmitted with an invalid later suffix. From 9000 every block must contain the producer's public-key commitment and satisfy the active difficulty rules. Compatibility is judged by block validity, not the software version name. At 9100, the exact P2WSH SHA256/preimage/CLTV spending template becomes available; this does not introduce a general-purpose script VM. Ordinary P2WPKH transfers and existing valid coins remain usable.

## Participation and privacy

P2P peers can observe connection IP addresses. The protocol does not guarantee participant anonymity.

---

[SUMUWW · A/B · Ed25519 · BLS](../../../CONNECTION_PROOFS_9000.html) · [HTLC · 9100](../../../HTLC_9100.html)
