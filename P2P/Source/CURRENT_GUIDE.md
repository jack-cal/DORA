# SUMUWW P2P Full / Light 0.3.6

Deposit SMW to sell or BTC to buy, including fees, into Trading wallet and wait
for confirmations. Publish checks available funds and reserves local inputs
per order. Trade beside an order rechecks funds and opens the prepared exchange.
Titles and free-text descriptions are removed. Every coin spend still requires
local review. This allocation is not on-chain escrow.

Peer discovery, reconnection and order synchronization are automatic. TLS 1.3
and authenticated bidirectional routes replace manual counterparty IP entry.
Both P2P programs must be updated. Internet operation requires reachable peers;
the application does not bypass every router or firewall.

Full requires synchronized local Bitcoin Core with txindex; Light verifies
headers and inclusion proofs and relies on servers for complete history. Both
require the current synchronized SUMUWW node. English remains the initial
language, with saved choices and all 34 languages retained.

Read [setup](BITCOIN_SETUP.md), [security and connection scope](NETWORK_SECURITY.md),
[edition differences](EDITIONS.md) and [verification](VERIFICATION.txt).
See [translated feature notes](docs/features/index.html) and the
[Full release](https://github.com/jack-cal/SUMUWW/releases/tag/p2p-full-v0.3.6) /
[Light release](https://github.com/jack-cal/SUMUWW/releases/tag/p2p-light-v0.3.6).
