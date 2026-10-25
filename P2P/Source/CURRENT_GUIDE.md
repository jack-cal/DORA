# SUMUWW P2P 0.3.4 guide

The current instructions are in [README.txt](README.txt), with changes in
[RELEASE_NOTES.txt](RELEASE_NOTES.txt) and evidence in [VERIFICATION.txt](VERIFICATION.txt).
Choose [Full or Light](EDITIONS.md): Full uses your local Bitcoin Core; Light
checks Bitcoin headers and inclusion proofs using configurable public TLS servers.
Both still use your local SUMUWW full node and can trade with each other.

SMW/BTC is the only supported trading pair. The board shares buy/sell posts
and coordinates conditional settlement. It is separate from peer discovery
and blockchain synchronization built into the full-node programs.

All 34 interface languages remain available; English is the default. Existing
full-node programs, ordinary wallets and stored blockchain data are unchanged.
Older trading wallets and recovery archives remain readable, preserving SMW/BTC
addresses, keys and records. Retired asset data remains encrypted but is inactive.

Valid legacy blocks through 8999 remain usable. Upgraded nodes reject old-rule
blocks at 9000 inclusive and later. Conditional-spend activation remains 9100.
Advertisements can be shared before that height; funding requires activation.

Public trading also requires a configured synchronized SUMUWW node and a working
Bitcoin connection for the selected edition,
a reachable counterparty, confirmations, transaction fees and timeout monitoring.
No separately deployed exchange contract is needed. Keep private recovery backups.

[Detailed Bitcoin full-node setup and block-9100 activation guide](BITCOIN_SETUP.md).

Current editions, 25 October 2026: P2P Full/Light 0.3.4 and Windows full node
0.57.46. Downloads:
https://github.com/jack-cal/SUMUWW/releases/tag/p2p-full-v0.3.4
https://github.com/jack-cal/SUMUWW/releases/tag/p2p-light-v0.3.4

## 0.3.4

Before broadcasting a signed SUMUWW transaction, P2P checks it against the connected node. A rejected check does not broadcast it. Agreed swap amounts and fees remain fixed; Bitcoin fees use their own units.

[Current features in 34 languages](docs/features/index.html).
