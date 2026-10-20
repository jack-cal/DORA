> **Archived document.** Preserved from the published documentation before consolidation. For current rules and instructions, see https://github.com/jack-cal/SUMUWW/tree/main/Documentation .

# SUMUWW v4 and the height-9000 boundary rule

Implementation reference: the random-10% source revision Windows 0.57.26 / Android 0.6.76, reviewed 2026-10-19. This describes the supplied code, not a claim of completed public-network activation or an independent security audit.

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
| `bpart` | Authenticated multipart transfer / 큰 경계 자료 분할 전송 |
| `bblock` | Carry a native block with its complete boundary envelope |

Boundary commands require authenticated v4 sessions. Large messages use ordered authenticated `bpart` fragments with 256-KiB data pieces and a complete-message digest. Whole proofs are not capped at 1 MiB. The `bblock` logical payload remains `uint32_le proof_length || canonical_JSON_proof || serialized_native_block`. Normal frame/block/transaction limits and per-peer traffic quotas remain separate.

## Source locations and operational checks

Implementation: `sumuww/boundary.py`, `boundary_crypto.py`, `boundary_runtime.py`, `boundary_state.py`, `chain.py`, `app_service.py`, `peer.py` and `wire.py`; Android bundles the same consensus modules. Separate boundary node keys are unrelated to wallet spending keys and must be retained with node state for safe signing continuity. Protect backups containing those private node keys.

Operators should check the installed version, selected public profile, activation height, actual authenticated peer sessions and boundary errors. A connected peer is not evidence that it is mining. A block's acceptance, chainwork and certificate validation are separate from saved addresses and discovery responses. Project-run isolated tests and device UI checks do not establish worldwide adoption or public-chain activation.


## Current source policy: random signature blocks from height 9000

This document describes the 2026-10-19 random-10% source revision, Windows 0.57.26 / Android 0.6.76. The existing packaged executables and APK still contain the earlier every-block signature policy. This source revision has not been installed on the user's PC or physical phone or published as a release. A separate audit APK is used only in an owned emulator.

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
