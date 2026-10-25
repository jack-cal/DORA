> Document edition 2.3, 26 October 2026. Source-block 9,600 activation.

# Automatic beacon generation recovery

First included in Windows 0.57.34 / Android 0.6.84; retained in Windows 0.57.47 / Android 0.6.96. This document describes a protocol extension;
it does not certify public-network readiness.

## What changes

The background engine can replace an unavailable distributed-randomness group,
prepare a fresh threshold key, and commit the complete public setup in an ordinary
mined block. Every node selects the latest valid setup in the source block's
ancestry. The old group does not have a veto over recovery.

This is **fresh key generation**, not reconstruction or redistribution of a lost
old secret. Old blocks and completed connection proofs remain verifiable under
their original setup. An unfinished old job keeps its original A/B hashes and
original beacon; a new key cannot finish that old job or redraw its lottery.

A verified threshold beacon selects a connection event with probability 20%. This is not a fixed five-block schedule or a guarantee of completed proofs. The producer probes its entire discovered identity inventory and samples three distinct responding identities without replacement. A response establishes availability at that round, not a promise of a later reply.

For source blocks at or above 9,600, a completed proof must include a certified active-candidate list. Activity signatures bind the network, A/B pair, recent round, anchored generation and nonce. More than two thirds of the PoW-anchored beacon generation must approve the complete responder set they independently observed; validators then recompute the three witnesses from the existing beacon. Signing requires a round on the active chain no more than six blocks behind the tip. Historical proof verification does not impose that freshness test.

Earlier valid proofs remain valid. After the tip reaches 9,600, an unfinished earlier job can use a new certified activity round while keeping its original A/B pair and event beacon. Earlier messages and signature pieces are archived; replies from different rounds are never combined. This does not reroll the 20% event lottery. A missing required quorum, an unavailable original beacon or a missing target producer may still prevent completion. Discovery has no registration fee, per-IP quota or fixed candidate count. One operator may run multiple identities. The certificate relies on the anchored quorum's honesty; it does not prove a worldwide complete census or independent human ownership.

## Preparation and failure handling

Each node probes all its discovered contacts through authenticated gossip, which
also reaches non-neighbors. It checks actual BLS shares on a fresh domain-separated
health challenge before treating the existing beacon as usable. A mere contact
reply is not proof that a secret share works.

Every responsive, locally eligible contact is included in a proposed DKG. All
listed dealers must contribute, and more than two thirds of the listed members
must sign readiness. If a dealer withholds a contribution or insufficient members
finish readiness, the attempt expires and a fresh proposal can use the responsive
remainder. A recipient which cannot authenticate/decrypt or verify a contribution
temporarily excludes that specific dealer from its own next DKG proposal. This
is a local observation; unsupported third-party accusations are not authority to
remove a node. Excluded contacts stay in discovery and are probed again; DKG exclusion alone
does not disqualify a responding contact from witness selection.

Default local scheduling uses a 60-second check interval, 20-second request timeout,
120-second setup timeout and 300-second DKG retry cooldown. These values do not
determine consensus or limit the witness candidate population. Unfinished link
jobs use a persisted exponential retry backoff capped at 900 seconds. Public deals/readiness are replayed
after reconnection. Secret shares and identity keys stay in the local key store.

## Consensus binding

The new DKG context has exactly `domain`, `network`, `root`, `members`, `previous`
and `round`. Its domain is `sumuww-dkg-recovery-v1`. `root` is the height-8999
ancestor (activation minus one in isolated tests). `previous` is the hash of the
latest setup-bearing ancestor, or 32 zero bytes for the first generation. `round`
is a prior ancestor hash on the same branch.

For a replacement, the round's height must be at least **12 blocks after** the
previous setup block. This is spacing between key generations, not a restriction
on random witness selection. The commitment itself comes in a later block.
Local silence is not asserted as a provable consensus fact. Any proposal meeting
the transcript and ancestry rules may be mined; ordinary valid cumulative work
resolves competing branches. Completed proofs retain the existing equal-work
tie-break rules.

Validators reject stale predecessors, a round from another branch, too-early
rounds, altered commitments, invalid readiness signatures and incomplete setups.
A stale local prepared setup is omitted from templates without stopping mining.
Reorganizations select the generation on the newly selected ancestry. A late
node gets the historical public setups in normal block synchronization, plus
complete paired proofs and conflicting side-branch evidence as before.

No setup, beacon response or witness response is a prerequisite for producing
the next PoW block. Crypto verification and transport still consume resources;
asynchronous processing does not promise zero CPU contention.

## Compatibility and limits

Earlier one-generation setup records and completed proofs remain valid. The
connection-proof message domain remains `sumuww-postpow-links-9000-v2` so historical
signatures retain their meaning. This does not make old executables compatible
with replacement setup blocks: **0.57.33 / 0.6.83 and earlier implementations need
an update before accepting the new recovery records**. Deploy compatible software
before the height-9000 transition; do not reset wallets or existing block history.

Recovery needs at least three usable DKG participants, a valid readiness quorum,
eventual message delivery and a future mined commitment. It cannot manufacture
available nodes, bridge a permanently disconnected network, guarantee progress
against unlimited malicious identities, or restore an old threshold secret when
too many old shares are permanently lost. Candidate completeness, resistance to
producer omission and unbiased DKG under arbitrary malicious participation are
not established by this change. It adds no central server or human-identity fee.

The construction uses the existing Feldman/threshold-BLS implementation; it is
not an independently audited DKG implementation. Background replacement is
distinct from same-key resharing described in general threshold systems. See the
[drand cryptography overview](https://docs.drand.love/docs/cryptography/) for the
underlying threshold-sharing concepts, not as certification of this code.

## Reproducing the checks

From the PC source directory with the pinned dependencies installed:

```text
python -m unittest tests.test_beacon_recovery.BeaconRecoveryTests
python tools/verify_beacon_recovery.py --work <new-empty-laboratory-directory>
```

The process fixture owns its regtest databases and loopback listeners. It does
not open production wallets. It uses shortened local timers and activation height
3; the consensus generation spacing, cryptography and 20% probability are unchanged.
The separate activation-prefix fixture tests the numeric 8999/9000 boundary using
an independently mined regtest history. Public Internet endurance and physical
Android device testing are separate from these checks.
