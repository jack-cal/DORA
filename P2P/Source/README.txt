SUMUWW 0.3.5 — update before block 9,600. See UPGRADE_9600.md and the local 34-language upgrade9600 guide.

SUMUWW P2P 0.3.5 — Full and Light Windows editions

CHOOSE AN EDITION
Full: run PC/SUMUWW-P2P-Full.exe with your synchronized local Bitcoin Core.
Light: run PC/SUMUWW-P2P-Light.exe; it checks Bitcoin headers and transaction
proofs using three configurable TLS servers, without a local Bitcoin Core.
Both editions still require your synchronized current SUMUWW full node.
They use separate default profiles and can trade with each other.
See EDITIONS.md for measured storage, verification differences and migration.

ACTIVATION AND SETUP
SMW/BTC conditional exchange transactions activate from SUMUWW block 9100.
The current synchronized SUMUWW full node is required in both editions.
Full additionally requires synchronized unpruned Bitcoin Core with txindex.
Light does not require local Bitcoin Core. Setup and ads can be used before
activation; they do not move coins. Read BITCOIN_SETUP.md for detailed setup,
storage, authentication, readiness checks, fees and recovery instructions.

ONE PAIR AND 34 LANGUAGES
Post buy/sell advertisements for SMW against Bitcoin (BTC). Choose the SMW
quantity and BTC price per SMW; the exact BTC total is shown before posting.
Both coins use eight decimals. Fractional smallest units are rejected rather
than rounded. Orders fill as a whole; partial fills are not supported.
English is the default; all 34 offline UI languages remain available.
No external translation service is used. Traditional Mongolian renders vertically.

RUN AND BACK UP
Extract the complete Windows ZIP and run its Full or Light EXE. Keep the _internal
directory beside the executable. The previous disposable BTC laboratory is
available in Full through --legacy-lab. Mainnet profiles use
%LOCALAPPDATA%/SUMUWW/P2P/Market (Full) or Market-Light (Light).
--test-market uses Market-Test or Market-Light-Test separately.
--data-dir chooses another profile. Existing ordinary/full-node wallets, keys,
coins and blockchain histories are not overwritten or automatically imported.

Create the separate encrypted trading wallet and retain its password.
Back up wallet saves the keys; Recovery backup also saves signed orders,
identity, agreements, encrypted transactions and connection settings. Restore
backup accepts either format in a new, empty profile. Restart locks the wallet.
A wallet-only backup does not replace ongoing trade recovery records.

DIRECT PEERS
Connect to the other participant using a reachable IP address and port. The
listener defaults to loopback; Internet access requires suitable binding,
routing and firewall configuration. There is no automatic Internet discovery,
NAT traversal or central marketplace. Synchronize fetches signed history.
Reservations require a direct route to the author. Canceled and reserved posts
remain in history. Signed post content is not proof of funds.

CHAIN CONNECTIONS
Configure both chains before preparing a trade:
* SMW: synchronized current full node, local authenticated RPC, conditional
  transfers active at height 9100. Height-9000 consensus activation is separate.
* BTC Full: local Bitcoin Core mainnet RPC/cookie, unpruned, txindex fully synced.
* BTC Light: select BTC in Connections, review the three TLS server addresses,
  then Save connection. The first sync downloads and verifies headers from
  genesis; progress appears below. No Bitcoin authentication file is required.
  At least two distinct server IPs must confirm the verified tip and supply
  consistent transaction data. A disagreement or insufficient responses stops
  funding. A failed server can be replaced by editing its address and saving.
  Light verification relies on honest, available servers for complete histories;
  it does not validate every Bitcoin transaction or prove a spend was not hidden.
Signing stays local. Private keys are never sent to peers or nodes. The trading
app reads chain evidence from these configured nodes; it is not itself a
Bitcoin full node. No separately deployed exchange contract is required.
Normal transaction fees and node operating costs still apply.

UPGRADING FROM 0.2.0 / 0.2.1
XRP, ETH and BNB markets are removed. New wallets contain only SMW and BTC keys.
Older encrypted wallets remain readable with the same password and supported
addresses. Inactive keys and old records remain in encrypted backups/recovery
archives; retired seeds are retained as opaque data and cannot sign in this app.
Old connection settings remain stored but are never contacted. Retired orders
are excluded from active listings and the outgoing feed. This version cannot
settle or refund retired-market trades; keep the original backup/software if
such a trade exists. Do not delete an unfinished trade to bypass a safety check.

TRADE FLOW
1. Publish a buy/sell post with SMW quantity, BTC unit price and details.
2. The other party reserves the whole order; reservation moves no coins.
3. Both prepare and exchange details. The signed agreement binds amounts,
   chains, proven keys, confirmation policy, hash and refund deadlines.
4. The SMW seller reviews and locks SMW first. The buyer verifies that confirmed
   lock before reviewing and locking BTC.
5. The seller verifies both locks and claims BTC. The buyer reads the revealed
   secret from Bitcoin and claims SMW, even without a peer claim notification.
6. Refresh status checks chain evidence. A peer cannot mark a trade paid.
Every spend requires local review. A peer cannot unlock, sign or broadcast.
The exact signed transaction is encrypted and saved before broadcast; retries
use that transaction. Network fees are additional to the order price.
There is no operator service fee.

Both mainnet chains require six confirmations. Initial refund deadlines are
SMW 48 hours and BTC 12 hours at target spacing, with a minimum six-hour safety
gap. Both use block heights and a 600-second target; actual elapsed time varies.
Keep monitoring while funds are locked.

CANCEL AND REFUND
Cancel my order closes an unreserved post. Cancel trade stops new local
funding and attempts to notify the peer; Exchange details can retry delivery.
It cannot reverse a confirmed transaction. Recovery records remain stored.
After the chain deadline, Refund returns unspent locked assets to the funding
key, less network fees. A completed claim cannot also be refunded. A valid
claim may still execute after cancellation while its chain conditions permit.
Refunds are explicit local actions, not an unattended service.

Unknown broadcast results remain pending, never completed. Automatic fee
replacement is not implemented. An insufficient fixed UTXO fee requires
inspection of the saved transaction. Unresolved operations are retained and
may block another trade from the same key. Keep passwords, recovery records,
node access and adequate balances for transaction fees.

HEIGHT 9000 / 9100
Valid legacy blocks through 8999 remain usable. Old-rule blocks at 9000
inclusive and above are rejected by upgraded nodes. Update miners and full
nodes. This app does not change issuance, halvings, DGW every ten blocks or
20% asynchronous connection proofs. Conditional transfers remain gated at 9100.

BUILD / VERIFY
Python 3.12: install requirements.txt and PyInstaller, then run build.ps1 for
both editions. run.py starts Full; run_light.py starts Light from source.
requirements-lock.txt records the exact test/build environment. For all tests:
PYTHONPATH=vendor;tests;. python -m unittest discover -s tests -v
--market-self-check --data-dir <new-directory> checks the packaged native UI,
all 34 languages, SMW/BTC wallet addresses and signed BTC-order reservations.
See VERIFICATION.txt for completed checks and precise limits.

## 0.3.5

Before broadcasting a signed SUMUWW transaction, P2P checks it against the connected node. A rejected check does not broadcast it. Agreed swap amounts and HTLC fee reserves remain fixed. Network fees use the current queue or a manual rate; a pending payment can receive a reviewed child-fee increase. Bitcoin uses its own fee units.

[Current features in 34 languages](docs/features/index.html).
