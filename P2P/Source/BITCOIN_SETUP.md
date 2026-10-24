# SUMUWW P2P: activation and Bitcoin setup

Applies to **Full 0.3.0** and **Light 0.3.0** for Windows. The only trading pair is
**SUMUWW (SMW) / Bitcoin (BTC)**. English is the default; all 34 interface
languages remain available.

## Trading activates at SUMUWW block 9100

**Conditional SMW/BTC exchange transactions become usable from SUMUWW block
9100 under the upgraded node rules.** Both editions check the current SUMUWW
node's activation status before preparing or funding a trade. Installing the
program, creating a trading wallet, connecting peers or posting an advertisement
does not bypass this rule. Those setup and board functions can be used earlier;
an advertisement or reservation by itself moves no coins.

This is a **SUMUWW height**, not a Bitcoin height. Reaching 9100 does not itself
provide a counterparty, balances, confirmations or a working Bitcoin connection.
The SUMUWW node must be synchronized and support the exact-template HTLC rules.
Use the current Windows full node from the
[SUMUWW releases](https://github.com/jack-cal/SUMUWW/releases/tag/pc-v0.57.40).

The earlier consensus upgrade remains separate: valid legacy SUMUWW blocks
through **8999 remain usable**; **old-rule blocks at 9000 inclusive and above
are rejected** by upgraded nodes. Update miners and validators. Issuance,
halvings, 20% asynchronous connection proofs and DGW every ten blocks are
unchanged. P2P 0.3.0 does not change those consensus parameters.

## Which edition needs a Bitcoin full node?

| Requirement | Full | Light |
|---|---|---|
| Current local SUMUWW full node | Required | Required |
| SUMUWW conditional-trade activation at 9100 | Required | Required |
| Your own synchronized Bitcoin Core | **Required** | **Not required** |
| Complete Bitcoin block history retained locally | Required, with transaction index | Not downloaded |
| Bitcoin evidence | Your Core validates the chain and supplies transactions | TLS servers supply headers, transactions and inclusion proofs |
| What this app checks | Agreed outputs and spending conditions against your node | Header work/difficulty, raw transaction contents and Merkle inclusion |

Each participant chooses an edition. Full and Light participants can trade with
one another. Full users operate their own Bitcoin Core; Light users depend on
available, honest data providers for complete transaction histories. Having a
counterparty run Core does not turn your Light client into a full validator.

The Full trading EXE **connects to Bitcoin Core; it is not itself a Bitcoin full
node** and does not contain a synchronized Bitcoin blockchain. Bitcoin binaries
included for the optional disposable test laboratory do not prepare mainnet.
There is no requirement to mine Bitcoin, deploy an Ethereum contract or rent
a server from SUMUWW. You can operate the required nodes on your own PC.

## Full: prepare Bitcoin Core

1. Obtain Bitcoin Core from its [official download page](https://bitcoincore.org/en/download/)
   and follow its release-verification instructions. The regression environment
   used Bitcoin Core 31.1; this is a test record, not a claim that any other
   version is compatible.
2. Choose a Bitcoin data directory with sufficient free disk space and keep
   Bitcoin on **mainnet**. This release requires the complete history and
   `txindex`; a pruned node is not supported by this trading adapter.
3. Configure the settings below in that data directory's `bitcoin.conf`. Merge
   them into existing settings, resolving conflicting options. Restart Core
   after changing its configuration. Do not replace or delete an existing
   wallet or data directory.
4. Let Core finish the initial block download, validation and transaction-index
   synchronization. A previously pruned installation must reacquire the missing
   history; merely changing `prune` does not restore deleted blocks. Follow Core's
   recovery instructions rather than deleting wallet files.

Example for a local mainnet installation:

```ini
server=1
txindex=1
prune=0
assumevalid=0

[main]
rpcbind=127.0.0.1
rpcallowip=127.0.0.1
rpcport=8332
```

`assumevalid=0` requests historical script verification without the optional
assume-valid shortcut and can increase initial synchronization time. `txindex=1`
allows transaction lookup needed for trade verification and recovery. `prune=0`
retains the block history needed to find spends. These settings do not enable
mining and do not send your trading private keys to Core.

Core creates a local `.cookie` authentication file while running. Select that
file in SUMUWW P2P; do not copy its contents into a post or send it to a peer.
For Core v31, the documented default Windows directory is
`%LOCALAPPDATA%\Bitcoin`, but a previously selected data directory may differ.
Use the directory actually shown by your Core installation. Keep RPC on the
local computer: do not forward port 8332 to the Internet. This RPC port is
different from Bitcoin's peer-to-peer port 8333.
See the official [configuration guide](https://github.com/bitcoin/bitcoin/blob/v31.0/doc/bitcoin-conf.md)
and [RPC authentication and security guide](https://github.com/bitcoin/bitcoin/blob/v31.0/doc/JSON-RPC-interface.md).

### Storage, download and operating costs

The Windows ZIP is only the application. Bitcoin's blockchain, transaction index
and SUMUWW's own database are **additional**. As a dated sizing reference, the
[AWS Bitcoin node guide](https://aws-samples.github.io/aws-blockchain-node-runners/docs/blueprints/bitcoin#storage-requirements)
reports about 970 GB at Bitcoin block 969306, including roughly 880 GB of blocks,
74 GB of transaction index and 14 GB of chain state, and recommends 1.5 TB of
storage. Sizes continue growing. That guide describes a cloud deployment; it
does not require you to rent cloud infrastructure for SUMUWW.

Allow room for growth, other applications and SUMUWW data. Initial download and
verification time depends on the PC, disk and connection; this release does
not promise a completion time. Node operators cover their own hardware,
electricity, disk and Internet usage. The application has no operator service
fee; the trading parties pay the relevant on-chain transaction fees.

### Connect Full and confirm readiness

1. Start your synchronized SUMUWW node and Bitcoin Core.
2. In **Connections**, select **SMW**, enter your node's local RPC address and
   authentication-file path, and save. Use your actual node settings.
3. Select **BTC**. For the example above, enter `http://127.0.0.1:8332/` and
   choose Core's `.cookie` file as the authentication file. Save the connection.
4. Resolve any synchronization or index error before preparing a trade. Keep
   both nodes available throughout funded trades and refunds.

For diagnosis, Core's read-only console commands `getblockchaininfo` and
`getindexinfo` show the state. Full requires `chain` to be `main`,
`initialblockdownload` to be false, `pruned` to be false, and
`txindex.synced` to be true. It also checks the Bitcoin genesis. The SUMUWW
connection must report the expected chain, synchronized state and height-9100
conditional-spend rule. Creating a Bitcoin Core wallet or importing the trading
private keys into Core is unnecessary: this app signs locally.

## Light: no local Bitcoin Core or complete history

Run `SUMUWW-P2P-Light.exe`, configure the same local SUMUWW connection, then select
BTC in **Connections**. Review the three editable Electrum TLS server addresses
and save. No Bitcoin RPC cookie is needed. The first synchronization downloads
and verifies Bitcoin headers from genesis. Progress and verified height appear
in the application; the interface stays responsive.

The measured raw header cache was **77,811,280 bytes, about 77.8 MB**, at Bitcoin
height 972640 on 2026-10-23. Application files, trading records, memory, temporary
replacement-cache space and SUMUWW data are additional. The initial header wire
download was about 155.7 MB because the protocol encodes headers as text.
Transactions and proofs are fetched as needed. These are measured sizes, not a
fixed lifetime storage limit. This client uses Electrum, not compact filters.

At least two distinct server IPs must agree on the verified tip and provide
consistent data. One of three servers may be unavailable while two consistent
responses remain. Conflicts or invalid proofs stop payment preparation.
Distinct IPs do not prove independent ownership. Merkle inclusion does not prove
history completeness or that no spend was hidden; Light does not validate all
Bitcoin transaction inputs and scripts. Servers can also learn which scripts
you query. Use Full when you need your own full Bitcoin validation. Read the
[edition comparison](EDITIONS.md) for the precise checks and limitations.

## Trading, cancellation and recovery

After activation and successful chain checks, publish a buy/sell post with the
SMW amount and BTC unit price. The other participant reserves the whole order.
Both review the same signed terms. The SMW seller funds first; the buyer checks
that confirmed lock before funding BTC. The seller claims BTC, revealing the
secret that allows the buyer to claim SMW. Both mainnet chains require six
confirmations. Each spend requires local review.

Cancellation can stop new funding; it cannot reverse a confirmed transfer or
bypass a refund deadline. Refunds return an unspent expired lock to its funding
key, less network fees. A claimed output cannot also be refunded. Refunds and
claims are explicit actions: there is no unattended monitoring or automatic fee
bumping. Keep the app, working chain connections and complete recovery records
available while funds are locked. Fixed fees may be insufficient in congestion.

Use **Recovery backup** to preserve keys, orders, agreements and saved signed
transactions. Wallet-only backups do not contain all funded-trade state. Full
and Light use separate profiles; restore a complete backup into an empty profile
to switch editions, and stop the previous copy. Do not run duplicate copies of
the same trading wallet concurrently. Existing ordinary-wallet and full-node
data are not automatically imported or replaced.

The order board uses directly reachable peer addresses. It has no hosted public
marketplace or automatic NAT traversal. Test-chain trades, mixed-edition trades,
cancellation and refunds passed the checks in [VERIFICATION.txt](VERIFICATION.txt).
Public Bitcoin checks were read-only; no mainnet funds were transferred in those
tests. The results do not constitute an independent security audit.
