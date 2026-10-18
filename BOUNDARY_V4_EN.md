# SUMUWW v4 and the height-9000 boundary rule

Implementation reference: Windows 0.57.24 / Android 0.6.74 boundary9000 candidate, reviewed 2026-10-19. This describes the supplied code, not a claim of completed public-network activation or an independent security audit.

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

## v4 transport

The existing 24-byte frame header, network magic, genesis/profile checks and `version` / `verack` handshake remain. Protocol values 1, 2, 3 and 4 are recognized. Discovery address exchange is available from v2; numeric IPv6 address hints from v3, including v4. The boundary-capable runtime first attempts v4 and has compatibility retry paths for older peers.

| Command | Purpose |
|---|---|
| `bhello` | Signed identity / BLS member binding to this socket's exchanged handshake nonces and network |
| `bquery` | Relay the signed parent-context discovery query |
| `bresponse` | Relay a query-bound signed responder record |
| `bcall` | Relay authenticated `ready` / `sign` calls and replies |
| `bblock` | Carry a native block with its complete boundary envelope |

Boundary commands require a negotiated v4 session and a completed boundary identity handshake. Control JSON rejects duplicate keys and unsupported values. Proofs are limited to 1 MiB. The ordinary payload limit is 4,000,000 bytes; command-specific limits allow `bblock` up to that limit plus 1 MiB plus 4 bytes and `bcall` up to 9 MiB. A `bblock` payload is `uint32_le proof_length || canonical_JSON_proof || serialized_native_block`. Ordinary 80-byte headers are unchanged. An ordinary unsigned `block` cannot substitute for a required certificate at or above 9000.

## Source locations and operational checks

Implementation: `sumuww/boundary.py`, `boundary_crypto.py`, `boundary_runtime.py`, `boundary_state.py`, `chain.py`, `app_service.py`, `peer.py` and `wire.py`; Android bundles the same consensus modules. Separate boundary node keys are unrelated to wallet spending keys and must be retained with node state for safe signing continuity. Protect backups containing those private node keys.

Operators should check the installed version, selected public profile, activation height, actual authenticated peer sessions and boundary errors. A connected peer is not evidence that it is mining. A block's acceptance, chainwork and certificate validation are separate from saved addresses and discovery responses. Project-run isolated tests and device UI checks do not establish worldwide adoption or public-chain activation.
