# SUMUWW P2P — SMW/BTC trading

[All components](../README.md) · [Full/Light comparison](Source/EDITIONS.md) · [User guide](Source/README.txt) · [Verification](Source/VERIFICATION.txt)

## Activation and Bitcoin requirement

**SMW/BTC conditional exchange transactions activate from SUMUWW block 9100.**
Full requires your own synchronized **unpruned Bitcoin Core with txindex**;
Light requires no local Bitcoin Core. Both require the current synchronized
SUMUWW node. Setup and ads can be used earlier, but they move no funds.

**[Read the detailed Bitcoin setup and block-9100 guide](Source/BITCOIN_SETUP.md)**
for disk space, download, configuration, local authentication, readiness checks,
Light's verification limits and funded-trade recovery.

## Current — 0.3.4

| Edition | Windows download | Release notes | Source |
|---|---|---|---|
| Full — your local Bitcoin Core | [Full Windows ZIP](https://github.com/jack-cal/SUMUWW/releases/download/p2p-full-v0.3.4/SUMUWW-P2P-Full-0.3.4-Windows.zip) | [Full release](https://github.com/jack-cal/SUMUWW/releases/tag/p2p-full-v0.3.4) | [Source ZIP](https://github.com/jack-cal/SUMUWW/releases/download/p2p-full-v0.3.4/SUMUWW-P2P-0.3.4-Source.zip) |
| Light — Bitcoin headers and transaction proofs | [Light Windows ZIP](https://github.com/jack-cal/SUMUWW/releases/download/p2p-light-v0.3.4/SUMUWW-P2P-Light-0.3.4-Windows.zip) | [Light release](https://github.com/jack-cal/SUMUWW/releases/tag/p2p-light-v0.3.4) | [Source ZIP](https://github.com/jack-cal/SUMUWW/releases/download/p2p-light-v0.3.4/SUMUWW-P2P-0.3.4-Source.zip) |

The current builds check signed SUMUWW transactions with the connected node before broadcast. Rejected checks are not broadcast. Agreed swap amounts and fees stay fixed; Bitcoin fees retain their own units. Current documentation is included in all 34 supported languages.

Both editions post signed SMW/BTC buy/sell orders with exact prices and quantities,
support locally reviewed conditional settlement and deadline refunds, and can trade
with each other. English is the default; all 34 offline UI languages remain available.
No ETH, BNB or XRP markets and no separately deployed exchange contract.

Full uses a synchronized, unpruned local Bitcoin Core with txindex. Light downloads
and checks headers from genesis and transaction inclusion proofs from configurable
TLS servers. Its measured header cache was about 77.8 MB; application files, trade
records, temporary space and SUMUWW data are additional. Light depends on honest,
available servers for complete histories and does not provide full Bitcoin validation.
Both editions require a current synchronized local SUMUWW full node and six confirmations
on each mainnet chain. Conditional funding is gated at height 9100.

Extract the complete ZIP and run the named EXE in PC. The Full and Light profiles
are separate. Use a complete Recovery backup when moving a funded trade; do not
run duplicate copies of the same wallet concurrently. See [migration and limits](Source/EDITIONS.md).

The board requires directly reachable counterparty addresses. There is no hosted
public orderbook, automatic NAT traversal, automatic fee bumping or unattended
refund service. Network fees apply. Tests used disposable assets; public checks
were read-only and do not establish a mainnet settlement audit.

## Upgrade before block 9,000

Valid legacy blocks through **8,999 remain usable**, including the valid prefix
of a mixed synchronization batch. **Old-rule blocks at 9,000 inclusive and above
are rejected** by upgraded nodes. Continued legacy mining does not extend the
upgraded chain. Update miners and validators. Wallet keys, valid coins, issuance,
halvings, the 20% asynchronous proof rule and DGW every ten blocks are preserved.
The separate HTLC spending activation remains **9,100**.

Earlier [0.1.9](https://github.com/jack-cal/SUMUWW/releases/tag/p2p-v0.1.9) and
[0.1.8](https://github.com/jack-cal/SUMUWW/releases/tag/p2p-v0.1.8) laboratory downloads
remain in release history. They are not the current Full/Light trading board.

## Version history

All published historical assets remain available. Older combined PC/Android releases are listed under both matching components; current platform releases are separate.

| Published (UTC) | Release | Application | Source |
|---|---|---|---|
| 2026-10-20 | [SUMUWW P2P 0.1.7 — Windows](https://github.com/jack-cal/SUMUWW/releases/tag/p2p-v0.1.7) | [Windows ZIP](https://github.com/jack-cal/SUMUWW/releases/download/p2p-v0.1.7/SUMUWW-P2P-0.1.7-Windows.zip) | [Source ZIP](https://github.com/jack-cal/SUMUWW/releases/download/p2p-v0.1.7/SUMUWW-P2P-0.1.7-Source.zip) |
| 2026-10-20 | [SUMUWW P2P 0.1.6 — Windows](https://github.com/jack-cal/SUMUWW/releases/tag/p2p-v0.1.6) | [Windows ZIP](https://github.com/jack-cal/SUMUWW/releases/download/p2p-v0.1.6/SUMUWW-P2P-0.1.6-Windows.zip) | [Source ZIP](https://github.com/jack-cal/SUMUWW/releases/download/p2p-v0.1.6/SUMUWW-P2P-0.1.6-Source.zip) |
| 2026-10-20 | [SUMUWW P2P 0.1.5 — Windows](https://github.com/jack-cal/SUMUWW/releases/tag/p2p-v0.1.5) | [Windows ZIP](https://github.com/jack-cal/SUMUWW/releases/download/p2p-v0.1.5/SUMUWW-P2P-0.1.5-Windows.zip) | [Source ZIP](https://github.com/jack-cal/SUMUWW/releases/download/p2p-v0.1.5/SUMUWW-P2P-0.1.5-Source.zip) |
