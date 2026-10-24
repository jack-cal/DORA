# Automatic beacon generation recovery

First included in Windows 0.57.34 / Android 0.6.84; retained in current Windows 0.57.40 / Android 0.6.89. This document describes a protocol extension;
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

Witness selection remains three distinct identities sampled from the producer's
entire discovered set. Recovery probes do not remove contacts from that set.
There is no registration, exit procedure, fee, per-IP quota or fixed-size witness
shortlist. The 20% event probability, issuance, halvings and DGW/10 are unchanged.

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
remove a node. Excluded contacts remain witness candidates and are probed again.

Default local scheduling uses a 60-second check interval, 20-second request timeout,
120-second setup timeout and 300-second DKG retry cooldown. These values do not
determine consensus or limit the witness candidate population. Unfinished link
jobs retry with a 30-second local backoff. Public deals/readiness are replayed
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
