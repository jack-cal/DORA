# SUMUWW Node Operation PC 0.57.46

SUMUWW PC program · 0.57.46

## New wallets and existing data

For the general user ZIP, extract the entire archive and run **SUMUWW.exe**. The default interface is English. The Language menu offers 34 languages. The UI selection is remembered on the next launch. English remains the default document language. The current integration update, API corrections, operations, examples and release introduction are available in all 34 UI languages at [Documentation](../../../docs/index.html). Close existing SUMUWW windows normally before using the new executable. The development commands and start.cmd examples below refer to the complete source distribution.

Extract the archive and run `start.cmd`. The default GUI network is SUMUWW. Keep the native SUMUWW.exe, SUMUWW-node.exe, and shared _internal folder together. Build verification is recorded in the versioned EXCHANGE_VERIFICATION.txt supplied with this release.

The existing registered SUMUWW data path and connection settings are retained. A new PC defaults to %LOCALAPPDATA%\SUMUWW\data; use `--directory` or SUMUWW_DATA_DIR to specify another location. Other nodes use separate DBs and data folders. Close the existing window before updating.

Automatic discovery uses enabled discovery sources and saved addresses. Manual peer entry is optional. Discovered addresses are untrusted hints: network, genesis, blocks and transactions are independently validated. A reachable operating SUMUWW peer is still required; discovery cannot create one.

## Connecting and listening

1. Run `SUMUWW.exe` for the wallet and full node.
2. Use automatic discovery. If it finds no reachable peer, optionally enter a known operating peer using its actual IP or domain and listening port; the port is not necessarily 18444.
3. Before mining, check actual peer connections and completed block synchronization. A count of 0 leaves mining waiting.

`0.0.0.0` is a listening address, not the address of a peer to connect to. Outbound DNS resolution checks IPv4 and IPv6 results against the connection policy and connects to an allowed numeric address. Stop mining before changing settings. Even with internet permission enabled, a connected-node count of 0 means no current connection to a remote SUMUWW node. TCP connectivity alone does not establish completed block synchronization.

The following example runs a node without the GUI. The first listening node can start without --peer; default GUI mining waits until another node connects and synchronization finishes. Replace HOST with the actual peer address.

```powershell
.\run.cmd peer --network sumuww --database data/server/node.sqlite --allow-internet --listen 0.0.0.0:18444 --peer HOST:18444
```

The firewall helper adds only the SUMUWW inbound rule and does not disable other rules. To reverse it, run `Remove-NetFirewallRule -Name SUMUWW-P2P-TCP-18444` in administrator PowerShell. The program does not automatically forward router ports.

## Mining, transfers, and storage

Mining requires a synchronized peer whose chain was verified recently. An additional peer whose chain has not yet been verified, or a normal live-block download, does not by itself stop mining while a recently verified synchronized peer remains usable. After full validation, a greater-work tip updates the mining candidate while the connection stays open. Mining waits if no recently verified synchronized peer remains; a user stop ends the request. A peer cannot certify the latest worldwide chain or independent mining power.

Mining refreshes candidates when the search space is exhausted and continues from a new valid tip when one with greater work arrives. A user stop cancels it. Mining time varies by computer and difficulty; 600 seconds is an average target. Rewards become spendable when spending height minus creation height is at least 100. The developer CLI's `--network sumuww mine` and `mine-test` do not allow standalone mining. Offline development mining uses the separate `regtest` and `retarget-lab` networks.

A transfer is relayed to peers and must enter a valid block to affect the confirmed balance. Recent transactions show confirmation counts; a branch change can change confirmation status. Balances on different branches are not added together.

On normal chain changes, the wallet calculates balances and transaction confirmations for the current active chain. A change of 6 or more blocks does not by itself show a general warning or automatically hold GUI/CLI transfers. Immediately before submission, sending revalidates current inputs, maturity, amounts, and signatures inside the SQLite write transaction.  `chain-safety.json` hold records are not applied to current transfers and require no manual release or acknowledgement. There is no need to edit or delete old hold files.

If the same actual connecting IPv4 or IPv6 address sends definitely invalid blocks, such as invalid difficulty/rewards/signatures, or malformed checksum/payload/header data 3 times within 600 seconds, the node restricts that IP's connections for 300 seconds. This applies to inbound and outbound connections together and tracks at most 128 IPs in memory. Normal valid branches, chain changes, equal work, unknown tips, ordinary mempool conflicts, temporarily future-dated blocks, and UnsupportedFeature do not count. Simple timeouts, disconnections, missing replies, and different network identifiers do not count either. After the restriction expires or the program restarts, the peer can reconnect without a permanent ban.

This connection restriction does not sanction miner identities or wallet addresses. Other nodes sharing the same IP can be affected, and changing IP can bypass it. It neither changes consensus nor rejects a private chain that follows all rules and has greater cumulative work. Recipients and exchanges validate deposits with a normal SUMUWW node and apply their own confirmation and operating policies. These distinctions are explained in [mining modifications and transaction confirmations](../../../docs/i18n/en/MINING_AND_CONFIRMATIONS.md).

Wallet files can be stored on another drive using file dialogs. To put the entire chain on removable storage, specify a location such as `start.cmd --directory "LOCAL_DATA_DIRECTORY"`. First close the program normally and retain the whole data folder. Copying only the executable to USB does not automatically move the default data path.

Windows wallet storage uses overwrite-protected rename without hard links. Physical FAT32/exFAT device tests and power-loss validation have not yet been performed. Both the file and password are required for restoration. A USB backup is not a hardware wallet. The external-signing interchange is available separately; vendor-specific hardware applications and physical-device validation are not supplied by this release.

All chain blocks and competing branches remain stored. There is no pruning or total-capacity limit, so maintain free disk space. regtest and retarget-lab are independent test networks; do not mix them with SUMUWW DBs, addresses, or wallets.

## Local RPC/API

The program provides opt-in, token-authenticated JSON-RPC 2.0 and HTTP REST interfaces at `127.0.0.1:18443`. The GUI saves the RPC/API enable setting and port. The node CLI also starts the service and supplies a local RPC client. They query the active chain, addresses and mempool, submit signed transaction/block bytes, and build mining templates. This release exposes no private-key export, wallet unlock or remote signing methods. Method names do not imply Bitcoin Core API compatibility. [RPC/API guide](i18n/en/RPC_API.md).

Fees equal total inputs minus total outputs. The GUI and wallet-send CLI now use automatic estimation by default; the sender may override it with any nonnegative manual total, including 0. The sender pays the fee in addition to the payment; the recipient receives the full specified amount. Included fees may be claimed by the block miner at the block reward address with the subsidy. There is no developer share, automatic burn or additional issuance. A higher fee can improve the chance of inclusion when blocks are congested, but does not change the target block interval or guarantee faster propagation or confirmation.

UI, API and performance improvements can preserve genesis, issuance, difficulty, signatures, UTXO validity and cumulative-work chain selection. Each node still validates independently; neither the author nor an API caller can force upgrades or mint, freeze or rewrite balances. Adoption of changed consensus rules is voluntary and may split the chain. These rules do not cryptographically prevent people from creating a fork. SUMUWW has a decentralized consensus architecture; sustained participation by independent public operators has not yet been established by the local checks.

SUMUWW's own code is distributed under the MIT license, the same license type used by Bitcoin Core. Use, copying, modification, merging, publication, distribution, sublicensing, sale and commercial use are permitted. Copies or substantial portions must retain the copyright and permission notice. The software is supplied without warranty; MIT does not require publishing modified source or paying royalties. External dependencies retain their own license notices. The English LICENSE text is authoritative. `Copyright (c) 2026 SUMUWW contributors`. [MIT](../../../LICENSE).

## Fee policy

The wallet previews automatic slow, normal and fast fee rates from the connected local node and shows the payment, fee and total debit before confirmation. A manual rate can be entered in yugeon/vB. The minimum relay rate is 1 yugeon/vB, the automatic total cap is 0.01 SMW, and the manual total cap is 1 SMW. The CLI supports --fee-mode and --fee-rate; its explicit --fee option is a total in SMW. Zero fees fail the default relay policy. These are local admission and wallet policies, separate from block validity.

Automatic estimation uses the current local pending queue, ancestor-package priority and block capacity. It does not sample fees from previous blocks or use a historical percentile. The fast, normal and slow modes use capacity budgets of 1, 3 and 6 blocks; these are not confirmation-time guarantees. Virtual size is ceil(weight/4), measured in vB. Coin amounts use yugeon: 1 yugeon = 0.00000001 SMW. A quiet queue keeps the minimum relay rate. The preview refreshes while the wallet is active; the confirmed payment retains its exact fee. A node that is disconnected or synchronizing may have an incomplete queue.

The GUI displays a prepared payment quote and submits that same payment after approval, without silently changing the fee. A quote expires after 120 seconds; locking the wallet or changing the wallet or network invalidates it. Changed inputs or chain conditions can require preparing and confirming again. Final submission revalidates the transaction against current UTXOs and maturity.

The default miner ranks eligible transactions by ancestor-package fee per virtual byte. Parents are counted with their children and placed first; equal-rate packages preserve arrival order. Block weight and signature-operation limits remain enforced. The default mempool rejects fees below 1 yugeon/vB, while consensus itself permits a valid zero-fee transaction in a block. A successful block producer claims the issuance subsidy plus included transaction fees. RPC/API provides 28 methods and 11 REST routes, including estimatefee.

## Public node setup

To accept connections, enable Internet access and select a listening interface and port. Automatic address mode reads eligible addresses from local network interfaces; a locally assigned global address does not prove that outside peers can reach it. For a node behind NAT, configure inbound firewall access and router port forwarding where needed, then set the optional public contact address to a reachable global numeric IPv4 or IPv6 address and port. Leave it empty if inbound access is not configured.

Manual public contact syntax is `IP:PORT` for IPv4 and `[IPv6]:PORT` for IPv6. It requires Internet permission and a non-loopback listener. Scoped or IPv4-mapped IPv6 addresses are rejected. The program does not query a public-IP service or configure a router. An advertised address is an untrusted discovery hint and grants no consensus authority.

```powershell
.\SUMUWW-node.exe peer --network sumuww --database data/server/node.sqlite --allow-internet --listen LISTEN_ADDRESS:18444 --advertise PUBLIC_CONTACT
```

Replace `LISTEN_ADDRESS` and `PUBLIC_CONTACT` with the interface and reachable endpoint for your own node. Enclose an IPv6 host in brackets when specifying its port.

Valid blocks through 8999 remain usable, including those sent together with an invalid later suffix. From 9000, every block needs a producer commitment. DGW uses 24 preceding blocks and recalculates at 9000, 9010, 9020…; intervening blocks keep the parent difficulty. The target interval remains 600 seconds. Connection events are random with probability 20%. Three discovered identities sign after PoW; mining and block acceptance do not wait for signatures. Cumulative work takes priority; valid, nonconflicting connections break work ties, followed by the smaller tip hash. Late evidence can change a tie. See the exact implementation and limitations below.

Tor and I2P are optional and bundled with SUMUWW. Only the selected router runs; Direct runs neither. No separate router installation or port setting is needed. If a private connection fails, it does not switch to Direct. I2P requires b32.i2p peers.

## Node interface

See [the integration guide](../../../EXCHANGE_INTEGRATION.md) for node API fields, transaction formats, validation, reorganization queries and isolated tests.
