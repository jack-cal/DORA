# P2P 0.3.6 network and funding behavior

## Connections

The mainnet application opens a dual-stack listener on an OS-assigned port.
Signed multicast announcements use group 239.255.83.77:18487, a short timestamp
window and the packet's actual RFC1918 source, never a payload-supplied IP.
Public BEP5 DHT lookup uses a separate SUMUWW market TLS3 namespace. Generic
DHT routers only supply contact hints and are not trading or payment services.
Public hints cannot target loopback, LAN, link-local, reserved or multicast
addresses. Runtime global interfaces can be announced; this does not prove
external reachability. No firewall rules, router mappings or UPnP settings are
changed. Offline, mutually blocked or isolated participants cannot trade until
a reachable route exists. No hosted bootstrap/trade relay is bundled.

TLS 1.3 authenticates an Ed25519 certificate key against the board identity.
The client signs a fresh server challenge; the server signs the client nonce.
Remembered endpoints pin their identity keys and reject changes. Discovery is
self-authenticated, not a claim about the human owner or trustworthy funds.
Sessions carry requests in both directions, including through an existing
shared peer. Routed trade payloads retain their origin signatures; routes have
a four-hop limit and never instruct a peer to dial an arbitrary supplied URL.
Direct peers can see each other's IP; relays can read routed trade metadata.
No coin private keys or secret preimages are sent in these messages.

Limits include 24 live peers, 8 concurrent handshakes, 32 concurrent queued or
running requests, 16 pending requests per session, 128 KiB frames, per-session
and aggregate rate limits, timeouts, bounded discovery hints and forwarding
queues. Malformed/unsigned packets never authorize a coin transaction. Plaintext
market protocol v2 is disabled; update both participants. The separate legacy
regtest laboratory remains a test-only tool and is not the mainnet transport.

## Funding and recovery

Posting requires an unlocked wallet and current confirmed outputs owned by its
paying key. The amount, claim/refund fee reserve, current funding fee and change
minimum must fit. Unconfirmed, immature, spent, previously allocated and pending
trade inputs are excluded. Local per-order allocations survive restart and
complete recovery backups; cancellation releases an unfunded allocation.
They are not blockchain escrow and cannot prevent a separate copy of a key from
spending. Maker and taker are checked again before reservation. Actual funding
is signed locally after review and checked by the configured node before broadcast.
Advertised amounts alone are not remotely proven balances.

Trade selects a full order, prepares the signed agreement and opens My trades.
The SMW seller locks first. After confirmations the buyer locks BTC; the seller
claims BTC and the buyer claims SMW. Uncertain results remain pending. Deadlines,
six-confirmation mainnet checks, explicit claims/refunds and write-ahead recovery
remain enforced. Network messages can exchange ownership proofs and signed
agreements, but cannot approve or broadcast a coin spend.
