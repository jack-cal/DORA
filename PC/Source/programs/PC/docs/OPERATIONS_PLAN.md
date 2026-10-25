# SUMUWW Basic Operation PC 0.57.23

SUMUWW PC program · 0.57.23

## Applied validation and operating policies

All received blocks and transactions are validated against the rules before entering the ledger. Invalid block outputs cannot be used as transfer inputs. Normal competing blocks and chain changes driven by greater valid work are handled; the number of changed blocks alone does not trigger a wallet warning or hold transfers. IP connection restrictions for repeated definite invalid data are a communication policy to reduce node load, not a substitute for coin validation or a way to identify miners.

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

Valid blocks through 8999 remain usable, including those sent together with an invalid later suffix. From 9000, every block needs a producer commitment. DGW uses 24 preceding blocks and recalculates at 9000, 9010, 9020…; intervening blocks keep the parent difficulty. The target interval remains 600 seconds. Connection events are random with probability 20%. Three discovered identities sign after PoW; mining and block acceptance do not wait for signatures. Cumulative work takes priority; valid, nonconflicting connections break work ties, followed by the smaller tip hash. Late evidence can change a tie. See the exact implementation and limitations below.

Tor and I2P are optional and bundled with SUMUWW. Only the selected router runs; Direct runs neither. No separate router installation or port setting is needed. If a private connection fails, it does not switch to Direct. I2P requires b32.i2p peers.
