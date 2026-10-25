# SUMUWW connection-proof protocol · heights 9,000 and 9,600

Protocol baseline at 9,000, certified candidate selection from source block 9,600. Locally prepared edition 2.3; publication is separate.

## History, money and compatibility

The genesis and all pre-9000 consensus rules remain unchanged. Valid history up
to 8999 is accepted even when an old peer advertises an invalid continuation.
Each body is validated and committed separately; rejecting a later body does
not roll back the accepted prefix. Existing unspent coins remain subject to
their original owner signatures and maturity. A peer's software age alone is
not evidence that a transaction or block is invalid.

The first 150000 heights have a subsidy of 50 SMW; at 150000 it becomes 25 SMW
and halves every 210000 heights, using integer atoms (100000000 atoms = 1 SMW).
Nominal issuance is 17999999.97690000 SMW; excluding the unspendable genesis
reward it is 17999949.97690000 SMW. Coinbase maturity remains 100 blocks.

## Difficulty and mandatory block data

Below 8064 the original 2016-block adjustment applies. From 8064 through 8999,
DGW v3 recalculates every block with the preceding 24 blocks on its own branch.
At 9000, 9010, 9020… it recalculates using the same 24-block algorithm; between
these heights the parent nBits is retained. The target interval is 600 seconds.
Nodes reject unexpected nBits even if the supplied hash meets an easier target.

Every block at height 9000 or above must contain exactly one zero-value coinbase
output with script `6a25 || 534d574c01 || producer_ed25519_public_key_32_bytes`.
The native header remains 80 bytes and uses SHA-256d PoW. Old miners which omit
this output are rejected at 9000, not at a random later height. Miners from an
intermediate revision can still produce blocks which satisfy all current rules;
there is no remotely trustworthy executable-version blacklist. A previous
probability policy's attachment is rejected without invalidating an otherwise
valid native block. A wrongly recalculated difficulty is rejected independently.

## Asynchronous connection evidence

PoW completion, native block acceptance and propagation do not require witness
or randomness replies. A source producer schedules a job for its block A and a
specific direct child B. The job keeps the exact A/B target across retries. A
verified threshold beacon selects a connection event when its 256-bit output
is less than floor(2^256/5). This is a 20% event probability, not a five-block
schedule or a guarantee that 20% of blocks obtain completed evidence.

A verified threshold beacon selects a connection event with probability 20%. This is not a fixed five-block schedule or a guarantee of completed proofs. The producer probes its entire discovered identity inventory and samples three distinct responding identities without replacement. A response establishes availability at that round, not a promise of a later reply.

For source blocks at or above 9,600, a completed proof must include a certified active-candidate list. Activity signatures bind the network, A/B pair, recent round, anchored generation and nonce. More than two thirds of the PoW-anchored beacon generation must approve the complete responder set they independently observed; validators then recompute the three witnesses from the existing beacon. Signing requires a round on the active chain no more than six blocks behind the tip. Historical proof verification does not impose that freshness test.

Earlier valid proofs remain valid. After the tip reaches 9,600, an unfinished earlier job can use a new certified activity round while keeping its original A/B pair and event beacon. Earlier messages and signature pieces are archived; replies from different rounds are never combined. This does not reroll the 20% event lottery. A missing required quorum, an unavailable original beacon or a missing target producer may still prevent completion. Discovery has no registration fee, per-IP quota or fixed candidate count. One operator may run multiple identities. The certificate relies on the anchored quorum's honesty; it does not prove a worldwide complete census or independent human ownership.

Each of the three witnesses signs the canonical network/parent/height/slot/
A/B/team/beacon message with Ed25519. Each 64-byte signature is split into two
32-byte halves. The three front halves form 96 bytes; the three back halves form
another 96 bytes. Each bundle uses zlib only if shorter, otherwise raw encoding.
Signature bytes are generally incompressible; compression is not guaranteed.
Both halves reconstruct all three signatures during verification. They are
signature evidence, not a newly generated private key.

The source producer signs the paired attachment and B's producer signs a receipt
binding that same attachment. Only a complete paired proof earns a score. Proofs
are persisted in `link_proofs` and relayed separately from immutable PoW bytes.
They refer to exact A/B hashes; completing them never changes either block hash.
Missing halves, forged signatures, altered target hashes and wrong ancestry fail
verification. Late nodes fetch the blocks, anchored randomness transcript and
complete proofs, including conflict evidence on side branches, and independently
reconstruct and verify signatures. Some jobs can remain incomplete indefinitely.

## Randomness and availability limits

The experimental randomness protocol uses Feldman DKG with encrypted shares and
threshold BLS output. Its public setup is committed in an ordinary PoW coinbase
after activation. A connection uses a setup anchored before its source block.
Any threshold of valid responses reconstructs the same result. Missing responses
below that threshold leave evidence pending; PoW continues. Initial setup still
requires every listed dealer's contribution and a readiness quorum. Background
recovery probes discovered contacts, retries failed DKG attempts and prepares
a fresh key with responsive participants. A replacement is bound to the previous
setup block and an ancestor round at least 12 blocks later, then committed in
a subsequent ordinary PoW block. Old proofs keep their original setup; the new
key applies only to later source blocks. Lost old secrets are not reconstructed.
Recovery needs enough responsive participants, eventual delivery and a mined
commitment. Mining never waits for the recovery process. See BEACON_RECOVERY.md.

## Chain selection and conflicts

Valid cumulative work is always primary. At equal work after activation, count
nonconflicting proven A/B edges contained in each branch; the greater count wins,
then the smaller internal tip-hash integer wins. Duplicate proofs for one edge
do not multiply its score. If distinct edges occupy one parent/height slot, all
edges in that slot score zero, including when all three witnesses double-sign.
Legacy keys retain their original slot lock. Certified rounds use a lock bound to the slot, A/B pair and selection digest; changing the round does not permit conflicting edges to gain weight.

There is no arrival-order finality lock. Late evidence or newly discovered
conflicts can change an equal-work choice; a valid greater-work branch wins.
Hidden evidence is not proven absent. These rules do not guarantee irreversible
finality, majority-hashrate immunity or prevention of all forks. Broadcast and
verification consume CPU, disk and network time; asynchronous scheduling does
not guarantee zero resource contention or unlimited hostile-load resilience.

## Other retained features and migration

Exact-template P2WSH SHA256/preimage/CLTV spends activate at 9100. Ordinary P2WPKH
transfers, existing wallet encryption, 34 UI languages, icons and layout remain.
The HTLC extension is not a general script VM or an automatic swap service.

The policy identifier is `sumuww-postpow-links-9000-v2`; new signing transport
uses protocol 5, with native-only fallback for compatible older peers. The
preactivation v1 database marker may migrate without rewriting blocks or UTXOs.
A database already containing incompatible post-activation history is refused
for explicit review. Do not delete it or reset a wallet to bypass this check.

The shipped implementation and isolated test evidence are not an independent
security audit or proof of worldwide decentralization. Initial public-network
activation at height 9000 has not occurred in these laboratory tests.

## Source map

`sumuww/link_crypto.py`: format, splitting, sampling and producer outputs.
`sumuww/link_beacon.py`: distributed setup and threshold responses.
`sumuww/link_runtime.py`: discovery, async jobs, request/response and gossip.
`sumuww/link_state.py`: proof verification, persistence and equal-work choice.
`sumuww/difficulty.py`, `profiles.py`, `chain.py`: native consensus and DGW cadence.
`tests/test_activation_prefix.py`: valid old prefix plus invalid new suffix.

The obsolete mandatory random-10% BLS policy, distinct-IP witness rule and
registered-history lock are superseded. They are not requirements of this release.
