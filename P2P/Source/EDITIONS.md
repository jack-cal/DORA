# SUMUWW P2P 0.3.0 — Full and Light

Both Windows editions share a signed SMW/BTC buy/sell board, exact prices and
quantities, local signing, encrypted recovery records and deadline refunds.
Full and Light participants can trade with each other. English is the default;
the same 34 offline interface languages and branding remain available.

| | Full edition | Light edition |
|---|---|---|
| Program | `SUMUWW-P2P-Full.exe` | `SUMUWW-P2P-Light.exe` |
| Bitcoin data provider | Your synchronized Bitcoin Core | Three configurable Electrum TLS servers |
| Bitcoin verification | Your Core validates blocks and transactions | Local header PoW/difficulty and transaction inclusion proofs |
| Complete Bitcoin history on your PC | Required; unpruned, with `txindex=1` | Not required |
| Bitcoin header storage measured | Part of Core's full data | 77,811,280 bytes at height 972,640 |
| SUMUWW connection | Current synchronized local SUMUWW full node | Current synchronized local SUMUWW full node |
| Default profile | `%LOCALAPPDATA%/SUMUWW/P2P/Market` | `%LOCALAPPDATA%/SUMUWW/P2P/Market-Light` |
| Dedicated Bitcoin Core needed locally | Yes | No |
| Keys and signing | Local encrypted wallet | Local encrypted wallet |

The Full trading application is a client of your full nodes, not a bundled
mainnet Bitcoin full node. The included Bitcoin binaries in the Full package
are used only by the optional disposable regtest laboratory.


[Detailed Bitcoin full-node setup and block-9100 activation guide](BITCOIN_SETUP.md).

## Light verification and availability

This release uses the Electrum 1.4 protocol, not BIP157 compact filters. It
downloads all 80-byte Bitcoin headers from genesis, checks their links, PoW,
expected difficulty and retargets, median times, future-time bound, activated
header-version requirements and cumulative work. It uses Bitcoin Core v31.0's
published mainnet minimum-work floor; no header validation is skipped. The best
verified work chain is retained across restarts. A reorganization replaces the
cache only after the competing branch passes validation and has more work.

Before trading, at least two configured servers at distinct connection IPs must
confirm the verified tip. Public connections require a valid TLS certificate and
the Bitcoin mainnet genesis. A tip over 24 hours old is refused. Duplicate host
entries do not count as independent connections. Different IP addresses do not
prove different ownership; choose independently operated servers.

Script history, output lists and raw transactions are compared across responsive
servers. At least two responses are required. Conflicting responses stop payment
preparation; a third server can be unavailable while two consistent servers
continue. Output values and scripts are read from the actual transaction, not
accepted from a balance claim. Confirmed transactions need Merkle proofs checked
against the locally verified header. Reorganizations invalidate cached proofs
when the relevant block changes. Invalid proofs are rejected.

This is SPV security, not complete Bitcoin consensus validation. Even matching
servers can collude or omit a spend. Merkle inclusion is not proof that no other
transaction exists, and the client does not validate every transaction's inputs
and scripts. Querying scripts also reveals transaction interests to the servers.
Use Full when independent full validation is required. No server receives wallet
passwords or private keys. The application never accepts remote signing commands.

If a server withholds data, disconnects or disagrees, review Connections, replace
the unavailable/faulty endpoint and retry. Do not delete a funded trade. Signed
transactions and recovery records are retained. A disagreement can delay claims
or refunds; availability is not guaranteed. Monitor both chains while funds are
locked and preserve working node access and recovery backups.

## Data size and observed public-network check

On 2026-10-23 the client checked all headers through height 972,639 against three
public TLS servers. Header storage was 77,811,200 bytes (about 77.8 MB decimal).
The initial wire transfer was 155,659,439 bytes because Electrum sends headers as
hexadecimal text. That download took 205.34 seconds on the test connection; it is
not a speed guarantee. A subsequent run checked height 972,640 and a confirmed
public transaction's raw bytes and Merkle proof without creating a wallet or
moving money. Header storage then measured 77,811,280 bytes.

Application files, wallet/trade records, memory and temporary replacement-cache
space are additional. A header-cache replacement may temporarily need a second
copy. The cache is checked again from genesis after restart. Other transaction
data is fetched as needed; it is not the entire Bitcoin transaction history.
Growth is about 4.2 MB of raw headers per year at target spacing. Old or very busy
scripts may take longer to query or exceed a server's history limit. SUMUWW's
local chain storage remains separate. These measurements do not imply that the
entire application needs only 77.8 MB of disk or RAM.

## Wallets, profiles and moving between editions

The two default profiles are separate. Installing Light does not open, copy or
change an existing Full wallet. Use **Recovery backup**, stop the old application,
then use **Restore backup** with the same password in a new empty profile of the
other edition. That preserves SMW/BTC keys, addresses, order identity, signed
agreements and encrypted transaction records. A wallet-only backup preserves
keys, not the complete state of a funded trade. Never run two independent copies
of the same trading wallet at once; their spend reservations are not shared.

Restoring Full records into Light substitutes the configurable light connection
for Bitcoin Core and preserves fee/confirmation policy. Restoring Light records
into Full requires configuring your local Bitcoin Core before further trading.
SUMUWW node access must also work on the destination PC. Restore rebuilds the
Bitcoin header cache from the network; the cache is public data, not a wallet
secret. Existing ordinary-wallet and full-node files are not automatically imported.

The published 0.1.9 laboratory's profile remains separate. This release does not
claim automatic migration of all historical laboratory wallets. Local 0.2.x
trading-wallet backups remain compatible. Retired ETH/BNB/XRP keys remain encrypted
but inactive; this release cannot settle or refund those retired markets.

## Activation and operating limits

Valid legacy SUMUWW blocks through 8,999 remain usable. Old-rule blocks at height
9,000 inclusive and above are rejected by upgraded nodes. Upgrade miners and
validators. Issuance, halvings, 20% asynchronous connection proofs and DGW every
ten blocks are unchanged. Conditional HTLC transfers have a separate activation
at height 9,100, and both editions refuse funding before it.

Both mainnet chains require six confirmations. Refund deadlines use heights:
SMW approximately 48 hours, Bitcoin approximately 12 hours at target block times,
with a minimum six-hour gap. Actual elapsed time varies. Cancellation cannot
reverse a confirmed transfer or bypass its deadline. Refunds and claims are
explicit local actions. There is no unattended watcher or automatic fee bumping.
The fixed fee budget may be inadequate during congestion; inspect an unresolved
saved transaction instead of deleting records or signing a conflicting trade.

The board uses direct reachable peer addresses. It has no hosted order book,
automatic Internet discovery or NAT traversal. Orders fill as a whole and are
not proof of available funds. There is no separately deployed exchange contract
or application operator fee; blockchain transaction fees and operating resources
still apply. Mainnet funds were not transferred in verification. Test success
does not establish an independent security audit or guaranteed settlement.

## References

- [Bitcoin SPV operating modes](https://developer.bitcoin.org/devguide/operating_modes.html)
- [Electrum protocol](https://electrum-protocol.readthedocs.io/en/latest/)
- [Bitcoin Core v31.0 chain parameters](https://github.com/bitcoin/bitcoin/blob/v31.0/src/kernel/chainparams.cpp)
- [Bitcoin Core proof-of-work rules](https://github.com/bitcoin/bitcoin/blob/v31.0/src/pow.cpp)
- [Electrum public server directory](https://github.com/spesmilo/electrum/blob/master/electrum/chains/mainnet/servers.json)
- [User instructions](README.txt), [changes](RELEASE_NOTES.txt), [verification](VERIFICATION.txt)
