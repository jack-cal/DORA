SUMUWW P2P 0.1.9 — Native Windows application

CURRENT FUNCTIONALITY
SMW/BTC orders and signed reservations can be shared directly with another
instance. Existing wallet addresses can be queried through a local node.
Exchange execution is restricted to isolated SUMUWW and Bitcoin Core regtest.
Public-money funding and swaps remain disabled. The separate SUMUWW node
0.57.34 / Android 0.6.84 upgrade adds HTLC validation at height 9100; installing
this P2P application does not activate public trading.

RUNNING ON WINDOWS
Extract the complete Windows ZIP and run SUMUWW-P2P.exe. It opens a native
desktop window without a browser or command prompt. Keep all extracted files
together. Data is stored in %LOCALAPPDATA%\SUMUWW\P2P. Existing orders,
identity and encrypted test-vault files are retained. Closing the window
stops application-owned work and leaves stored records in place.

WALLET ADDRESS QUERIES
In the wallet-query view, select SMW or BTC, enter the local RPC URL, the
matching node authentication-file path and an existing receiving address.
SMW normally uses http://127.0.0.1:18443/rpc with its RPC token file.
Bitcoin Core normally uses http://127.0.0.1:8332/ with its .cookie file.
Use the actual ports and files configured for your local nodes. The app does
not enable RPC or change firewall settings. Authentication is read from the
local file, not embedded in URLs or sent to peers. Queries are manual and
read-only: no wallet unlock, private-key export or transfer is requested.
Bitcoin address queries report the selected P2WPKH address's UTXO balance,
not the sum of an entire wallet. Saved links contain address and file-path
settings. Querying an address does not enable public swaps.

DIRECT PEER CONNECTIONS
Enter the other instance's reachable IPv4/IPv6 address and port in the
connection view. The listener defaults to loopback. External inbound use
requires a reachable bind address, port and suitable network configuration.
There is no automatic Internet discovery, NAT traversal or public relay.
Orders, cancellations and reservations are Ed25519-signed and saved in
SQLite. Order quantities and the total BTC price are chosen by the user.
The operator service fee is 0%; blockchain transaction fees are separate.
Reservation is an agreement record, not a transfer.

ISOLATED TEST VAULT
Create a vault with a password of at least 12 characters and its confirmation.
Different random secp256k1 keys are used for SMW and BTC. The vault uses
AES-256-GCM and scrypt (N=32768, r=8, p=1), with random salt and nonce.
Back up wallet-regtest.vault privately. Both its backup and password are
required for recovery. Existing vaults are not overwritten. Restart locks
the vault; locking prevents new signatures, while previously approved work
can complete. Test addresses use drt for SMW and bcrt for Bitcoin.
These are test addresses, not public-chain deposit instructions.

TWO-PARTY REGTEST EXCHANGE
Each participant holds and signs with their own local test keys; the other
participant's private keys are not imported. Both sides must use compatible
local chain histories and authenticated RPC services. Bitcoin public-network
nodes are rejected for exchange execution. Standard SUMUWW node query and
transaction RPCs are supported alongside the research RPC adapter.
1. Select the same signed reservation, prepare local keys and exchange terms.
2. The SMW seller locks their test asset after preparing a signed refund.
3. The BTC buyer verifies the actual SMW lock before locking their BTC.
4. The seller verifies both actual locks and claims the BTC test output.
5. The buyer extracts and validates the secret from Bitcoin chain data and
   claims the SMW output; a peer completion notice is not sufficient.
6. After the refund height, each owner can broadcast their saved refund
   without the other peer or an unlocked vault, including after restart.
Every spending step requires the local user's action. Remote messages do not
unlock a vault or initiate spending. Retries use the same saved transaction.
Keep refund records and access to nodes that can query/broadcast transactions.

TEST POLICY
One confirmation, a 40-block SMW refund margin, a 15-block BTC margin and
fixed test fees are accelerated-regtest settings, not public-money policy.
Public fee estimation, confirmation/reorg policies and refund timing are
not enabled by this build. This application is not a custodial exchange.
The source ZIP contains implementation, tests and build files. GitHub's
automatic source archives contain the documentation repository instead.
Compare SHA256SUMS.txt with the downloaded files before use.

LANGUAGE SETTINGS
English first-launch default. Select any of 34 bundled languages; the choice is stored locally and restored. Switching language preserves entered quantities, order side, current tab, connection settings and records. Traditional Mongolian captions use the included licensed font.

UPGRADE AT HEIGHT 9000
Valid legacy blocks through 8999 remain usable. Old-rule blocks at 9000 inclusive and above are rejected by upgraded nodes. Update miners and validating nodes. See CURRENT_GUIDE.md.
