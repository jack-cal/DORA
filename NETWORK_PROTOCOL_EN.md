# SUMUWW TCP Protocol

<!-- boundary-v4-9000 -->
## v4 / height 9000 — implementation update

The general PoW branch examples below describe the rules before height 9000. From height 9000, compatible software also requires a complete boundary certificate; from 9001 it verifies the split connection to the signed parent. Three distinct node identities with three distinct observed IP addresses sign, and their BLS signatures are aggregated. Signatures do not add PoW weight. A candidate conflicting with this node’s registered connections is rejected. Discovery does not prove that every worldwide live node was included, and complete protection against 51% attacks has not been established. The detailed implementation, replacement rules, persistence and compatibility requirements are documented in BOUNDARY_V4.

[BOUNDARY_V4](BOUNDARY_V4_EN.md)
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
