# SUMUWW PC 0.57.46 RPC and HTTP API

SUMUWW PC program · 0.57.46

## Enable and authenticate

Open RPC/API in SUMUWW, enable the service and apply port `18443`. It is disabled until you opt in and binds only to numeric loopback `127.0.0.1`. Your saved enable/port settings are restored on the next launch. The default token file is `rpc-token` in the selected data directory. It contains a randomly generated 32-byte token encoded as 64 lowercase hexadecimal characters. Treat this file as a local access credential: an authenticated caller can submit transactions/blocks and request templates, but cannot unlock a wallet or sign. Status output does not reveal the token. The service does not enable public HTTP listening or change P2P firewall rules. For a node without the GUI:

```powershell
.\SUMUWW-node.exe peer --database data/server/node.sqlite --network sumuww --listen 0.0.0.0:18444 --allow-internet --rpc --rpc-port 18443 --rpc-token-file data/server/rpc-token
```

## Local command-line client

Run the client against the same local service and its token file. Use the actual token path of the GUI or daemon you enabled. `--params` is JSON and may be an object with named parameters or an array in the order below. Use an integer for height, limit and offset; `verbose` must be a JSON boolean. Specify the configured port when it differs from `18443`. `--params-file PATH` reads parameters from a UTF-8 JSON file, including a BOM. Use only one of `--params` and `--params-file`.

```powershell
.\SUMUWW-node.exe rpc --token-file data/server/rpc-token getblockchaininfo
'{"height":0}' | Set-Content -Encoding utf8 -Path rpc-params.json
.\SUMUWW-node.exe rpc --token-file data/server/rpc-token --params-file rpc-params.json getblockhash
```

## JSON-RPC 2.0

Send `POST /rpc` with `Content-Type: application/json` and `Authorization: Bearer <token>`. JSON-RPC requests use `"jsonrpc":"2.0"`, `method`, optional object/array `params` and a response `id`. A valid notification omits `id` and has no response body; HTTP returns 204. Batches contain at most 16 requests. A normal request receives `result` or `error` with its original `id`. This is SUMUWW’s own API contract; it does not claim Bitcoin Core RPC or BIP22 mining-format compatibility.

```json
{"jsonrpc":"2.0","id":1,"method":"getblockhash","params":{"height":0}}
```

```json
{"jsonrpc":"2.0","id":1,"result":"00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97"}
```

```python
from sumuww.rpc_client import call
result = call("http://127.0.0.1:18443/rpc", "data/server/rpc-token",
              "getblockchaininfo")
print(result)
```

## Methods and parameters

getmempoolinfo and GET /api/v1/mempool/info return one consistent read snapshot. Integer fields are size, bytes, max_transactions, max_bytes, remaining_transactions and remaining_bytes; full is Boolean. This version has 28 RPC methods and 11 REST routes.

MempoolFull is temporary local-capacity rejection: JSON-RPC -32005 and HTTP 503. The rejected transaction is not queued or accepted. Retry when capacity becomes available; this does not guarantee confirmation.

| Method | Parameters |
|---|---|
| `getblockchaininfo` | `{} / []` |
| `gethtlcinfo` | `{} / []` |
| `getspendinginfo` | `{} / []` |
| `getdatarecords` | `blockhash, offset, limit` |
| `decodescript` | `hex` |
| `gettxout` | `txid, index, include_mempool` |
| `findspendingtransaction` | `txid, index, start_height` |
| `getnetworkinfo` | `{} / []` |
| `getblockcount` | `{} / []` |
| `getbestblockhash` | `{} / []` |
| `getblockhash` | `height` |
| `getblock` | `hash, verbose` |
| `getrawmempool` | `{} / []` |
| `getmempoolinfo` | `{} / []` |
| `getmempoolpolicy` | `{} / []` |
| `estimatefee` | `vsize, mode` |
| `testmempoolaccept` | `hex` |
| `getmempoolentry` | `txid` |
| `gettransactionstatus` | `txid` |
| `getrawtransaction` | `txid, verbose` |
| `decoderawtransaction` | `hex` |
| `validateaddress` | `address` |
| `listunspent` | `address, limit, offset` |
| `getaddressbalance` | `address` |
| `sendrawtransaction` | `hex` |
| `submitblock` | `hex` |
| `getblocktemplate` | `address` |
| `help` | `{} / []` |

## HTTP REST routes

All routes below require the same Bearer token. GET returns JSON. POST takes exactly the shown JSON keys and goes through the same node validation as RPC. Replace route placeholders with an actual height, display hash, TXID or valid address of the selected network. There is no browser CORS permission; Origin/Referer requests are rejected. Use a local CLI or service client.

| Verb | Route | JSON body |
|---|---|---|
| `GET` | `/api/v1/info` | `—` |
| `GET` | `/api/v1/network` | `—` |
| `GET` | `/api/v1/mempool` | `—` |
| `GET` | `/api/v1/mempool/info` | `—` |
| `GET` | `/api/v1/blocks/{height-or-hash}` | `—` |
| `GET` | `/api/v1/transactions/{txid}` | `—` |
| `GET` | `/api/v1/addresses/{address}/balance` | `—` |
| `GET` | `/api/v1/addresses/{address}/utxos?limit=100&offset=0` | `—` |
| `POST` | `/api/v1/transactions` | `{"hex":"..."}` |
| `POST` | `/api/v1/blocks` | `{"hex":"..."}` |
| `POST` | `/api/v1/mining/template` | `{"address":"..."}` |

## Amounts, confirmations and maturity

Money fields ending in `_units` are integer minimum units. Fields ending in `_smw` are fixed 8-decimal strings; do not parse or sign using binary floating-point amounts. 1 SMW is `100000000` units. Confirmations follow the current active chain and can change after a valid reorganization. Coinbase outputs may be spent only when spending height minus creation height is at least 100. Balance/UTXO spendability is assessed for the next block and excludes inputs reserved by pending transactions. Addresses do not grant spending authority. External applications construct and sign transactions outside the node, then submit serialized signed bytes. See [the node integration contract](../../../EXCHANGE_INTEGRATION.md). The node RPC never handles wallet secrets. Existing wallet-send combines signing and local submission; it is not the offline signing command.

Fees equal total inputs minus total outputs. The GUI and wallet-send CLI now use automatic estimation by default; the sender may override it with any nonnegative manual total, including 0. The sender pays the fee in addition to the payment; the recipient receives the full specified amount. Included fees may be claimed by the block miner at the block reward address with the subsidy. There is no developer share, automatic burn or additional issuance. A higher fee can improve the chance of inclusion when blocks are congested, but does not change the target block interval or guarantee faster propagation or confirmation.

## Limits and errors

The server limits request bodies to `8004096` bytes, headers to `8192` bytes, batches to 16 calls, concurrent requests to 16 and a request deadline to 10 seconds. `limit` is 1–1000; `offset` is 0–1000000. HTTP Host must be numeric loopback and match the actual port. Authentication precedes execution. Unsupported routes, invalid JSON, wrong parameter types and malformed or invalid transaction/block data are rejected. A `getblocktemplate` request for `sumuww` requires a connected, fully synchronized peer; offline regtest is permitted. Templates provide `height`, `previousblockhash`, `bits`, `target`, `header_hex` and `block_hex`. Miners must satisfy normal PoW and all block rules before submitting; this endpoint neither lowers difficulty nor issues coins by itself.

JSON-RPC errors: `-32700` parse error, `-32600` invalid request, `-32601` unknown method, `-32602` invalid parameters, `-32603` internal error, `-32001` not found, `-32002` validation failure, `-32003` not running/mining gate, `-32004` batch response limit, `-32005` temporary local mempool capacity rejection. A successful submission is not an irreversible confirmation or guaranteed active-chain inclusion. Read the returned state and current chain confirmations.

## License and consensus

SUMUWW's own code is distributed under the MIT license, the same license type used by Bitcoin Core. Use, copying, modification, merging, publication, distribution, sublicensing, sale and commercial use are permitted. Copies or substantial portions must retain the copyright and permission notice. The software is supplied without warranty; MIT does not require publishing modified source or paying royalties. External dependencies retain their own license notices. The English LICENSE text is authoritative. `Copyright (c) 2026 SUMUWW contributors`. [MIT](../../../LICENSE).

UI, API and performance improvements can preserve genesis, issuance, difficulty, signatures, UTXO validity and cumulative-work chain selection. Each node still validates independently; neither the author nor an API caller can force upgrades or mint, freeze or rewrite balances. Adoption of changed consensus rules is voluntary and may split the chain. These rules do not cryptographically prevent people from creating a fork. SUMUWW has a decentralized consensus architecture; sustained participation by independent public operators has not yet been established by the local checks.

## Fee policy

The wallet previews automatic slow, normal and fast fee rates from the connected local node and shows the payment, fee and total debit before confirmation. A manual rate can be entered in yugeon/vB. The minimum relay rate is 1 yugeon/vB, the automatic total cap is 0.01 SMW, and the manual total cap is 1 SMW. The CLI supports --fee-mode and --fee-rate; its explicit --fee option is a total in SMW. Zero fees fail the default relay policy. These are local admission and wallet policies, separate from block validity.

Automatic estimation uses the current local pending queue, ancestor-package priority and block capacity. It does not sample fees from previous blocks or use a historical percentile. The fast, normal and slow modes use capacity budgets of 1, 3 and 6 blocks; these are not confirmation-time guarantees. Virtual size is ceil(weight/4), measured in vB. Coin amounts use yugeon: 1 yugeon = 0.00000001 SMW. A quiet queue keeps the minimum relay rate. The preview refreshes while the wallet is active; the confirmed payment retains its exact fee. A node that is disconnected or synchronizing may have an incomplete queue.

The GUI displays a prepared payment quote and submits that same payment after approval, without silently changing the fee. A quote expires after 120 seconds; locking the wallet or changing the wallet or network invalidates it. Changed inputs or chain conditions can require preparing and confirming again. Final submission revalidates the transaction against current UTXOs and maturity.

The default miner ranks eligible transactions by ancestor-package fee per virtual byte. Parents are counted with their children and placed first; equal-rate packages preserve arrival order. Block weight and signature-operation limits remain enforced. The default mempool rejects fees below 1 yugeon/vB, while consensus itself permits a valid zero-fee transaction in a block. A successful block producer claims the issuance subsidy plus included transaction fees. RPC/API provides 28 methods and 11 REST routes, including estimatefee.

## Exact integration semantics

The 20 method names and parameter contract are also supplied in
[API_CONTRACT.json](../../../API_CONTRACT.json). SUMUWW is not a Bitcoin Core RPC
implementation. A block or transaction lookup returns native SUMUWW objects.

- Primary money strings end in `_smw`, and exact integer fields end in `_units`.
  `_dora` aliases are retained for older clients. There is no `_sumuww` amount field.
  The public selector `sumuww` and the internal network value `dora` identify the
  same registered network; compare the expected genesis as well as its label.
- `gettxout` returns `value_units`, `script_pubkey`, `confirmations`, and `coinbase`,
  or null. It has no `spendable` field and does not filter immature coinbase outputs.
  A coinbase output is spendable in the next block when confirmations are at least
  100. The default `include_mempool=true` hides outputs spent by pending transactions;
  it does not add unconfirmed newly created outputs to the confirmed UTXO set.
- `listunspent` includes `coinbase`, `mature`, `pending_spent` and `spendable` for
  each output. Filter `spendable`; the list also contains unavailable outputs.
  Its pages can observe different revisions. Verify the tip before and after a
  multi-page operation and revalidate selected inputs before submission.
- `getaddressbalance` returns `confirmed`, `mature`, `immature`, `pending_spent` and
  `available` amounts as `_units` and `_smw`. It does not include new mempool outputs
  as confirmed incoming money. Maturity/spendability applies to the next block.
- `getrawtransaction` searches the active chain and mempool. Missing/orphan-only
  data returns -32001. A pending view has confirmations 0 and in_mempool true;
  a confirmed view includes height and blockhash. Inputs contain outpoints, not
  sender address fields. Outputs include index, value_units, value_smw and script_pubkey;
  address is included only when the output is encodable as a supported address.
- `getblock` returns an ordered txid list and the raw block. It accepts a Boolean
  verbose flag, not Bitcoin Core verbosity levels. A stored inactive block has
  active false and confirmations -1. Its raw transactions remain accessible by
  that block hash even when getrawtransaction no longer finds them.
- `findspendingtransaction` searches confirmed active-chain transactions from
  start_height, not pending transactions. A null result alone does not show that
  an output is currently available. Use gettxout with pending-spend filtering.
- `sendrawtransaction` rejects an exact duplicate with -32002 at the raw RPC level.
  On a timeout, query/retry the same signed transaction instead of generating a new
  payment. The external caller owns retry policy; node submission performs
  atomic validation against current state.
- Confirmation counts and active flags are observations that can change after a
  reorganization. There is no per-transaction execution receipt/status code for
  ordinary transfers: an accepted active-chain transaction has passed validation.

See [the integration guide](../../../EXCHANGE_INTEGRATION.md) and its executable
source-only regtest example for signed submission, rejection, confirmations, reorgs and data persistence.

## Node-only integration boundary (0.57.46)

`validateaddress` returns `isvalid=false` for invalid or wrong-network strings, or `isvalid`, canonical `address`, `script_pubkey` and internal `network` for valid addresses. Non-string parameters return -32602.

`decoderawtransaction` returns the ordinary transaction fields plus `validation=decoded_only`. It omits `confirmations`, `in_mempool`, `height` and `blockhash`. Parsing unsigned bytes succeeds when the serialization is valid; this does not validate the signature, UTXO availability, consensus acceptance or chain membership. Decoding does not submit or change state.

OP_RETURN data remains in transaction and block bytes, is queryable, and is excluded from spendable outputs. Native spending supports P2WPKH and the activated exact HTLC contract. This release changes no consensus, data-carrier or script rules.

## Yugeon, fee policy and transaction replacement

1 SMW = 100,000,000 yugeon; one yugeon is 0.00000001 SMW. Existing `_units` integer fields are yugeon. Serialization and balances are unchanged. A vB measures transaction data, not currency: `ceil(weight / 4)`. Fee rates are shown as yugeon/vB; policy API rates use yugeon per 1,000 vB.

The public node's default relay floor is 1 yugeon/vB. Regtest defaults to zero for controlled tests. This is local admission policy, not block consensus: a valid zero-fee transaction in a block remains valid. Refusal does not debit confirmed funds. An unconfirmed transaction can reserve local wallet inputs until it is confirmed or removed.

Automatic suggestions use the current accepted local mempool, including ancestor packages. Past block fee samples and price percentiles are not used. The estimator compares the volume ahead of a new transaction with available block size and signature-operation capacity, reserving space for the current coinbase and block header. A quiet queue uses the local relay floor, at least 1 yugeon/vB. Fast, normal and slow target the capacity of 1, 3 and 6 blocks respectively; these are estimation budgets, not confirmation deadlines. Package fees are divided by their combined vsize, with shared ancestors counted once. If the queue exceeds the selected budget, the suggested rate exceeds the boundary package by the smallest 0.001 yugeon/vB step. Actual transaction size is recalculated during payment preparation. Automatic fees remain capped at 0.01 SMW; manual wallet fees retain the 1 SMW cap. A cap may prevent the requested priority. These limits are wallet policy, not block validity.

The preview is read-only: PC status refreshes approximately every second, Wallet PC every four seconds, and Android every five seconds while active. A changed queue, replacement, new block or reorganization invalidates the cached queue. The final confirmation holds the exact signed fee; subsequent preview updates cannot reprice or replace it. Manual rate input is preserved. Observations describe this node's accepted transactions, not a global mempool. Offline or synchronizing nodes may have an incomplete view. No confirmation time is guaranteed.

`estimatefee(vsize, mode)` returns `source="live_mempool"`, `target_blocks`, `capped` and a `congestion` object. Its `rates` map is a 140-vB preview; the outer fee is calculated for the requested vsize. `pending_vsize`, `pending_count`, `block_vsize_capacity` and signature-operation fields describe the current snapshot. `sample_count` now counts pending transactions only. `backlog_change_vb_per_second` is a diagnostic net queue change measured over at most 60 seconds of process observations, or null during warm-up; it is not an arrival forecast and does not change the fee. An observation gap over 15 seconds resets this diagnostic window. Application `status.fees` exposes the same unsigned preview. No signing API is called by preview refreshes.

The wallet shows the final fee and total in SMW before confirmation and submits those exact signed bytes. Ordinary wallet submission cannot silently replace a competing transaction. A deliberately supplied RBF transaction is validated atomically, pays the fees of all removed descendants plus at least 1 yugeon per replacement vB, and must improve the rate over every direct conflict. It may remove at most 100 transactions and cannot add a new unconfirmed input. Pool limits remain 1,000 transactions and 4,000,000 serialized bytes. Invalid replacements leave the previous pool intact. Local replacement history retains at most 1,000 entries; it is not a complete network history.

| RPC | Parameters | Result |
|---|---|---|
| `estimatefee` | `vsize=140, mode="normal"` | Suggested integer yugeon fee, rate, sample count, source and cap status |
| `getmempoolpolicy` | none | Relay floor, incremental rate and replacement bound |
| `testmempoolaccept` | `hex` | Check signed bytes without queuing or relay; `allowed` and rejection details |
| `getmempoolentry` | `txid` | Exact local fee, virtual size, dependencies and descendant count |
| `gettransactionstatus` | `txid` | `confirmed`, `mempool`, locally `replaced`, or `unknown`, with the current tip |
| `getdatarecords` | `blockhash, offset=0, limit=100` | OP_RETURN output scripts in transaction/output order, active flag and tip |
| `getspendinginfo` | none | Implemented template limits and actual activation state |
| `decodescript` | `hex` | Canonical witness template, address and activation metadata; no ownership assertion |

`getdatarecords` returns the full script, not an interpreted token balance. A side-branch block is readable with `active=false`; record order is meaningful only within the stated block and chain snapshot. Check the returned tip across pages. The transaction and block weight bounds remain unchanged.

## Multisig and output locks

`sumuww.spending.SpendingTemplate` constructs and parses exact witness-v0 P2WSH templates. It accepts one to sixteen distinct compressed secp256k1 public keys, a signature threshold and an optional absolute height/time or relative height/time lock. Signatures commit to all inputs and outputs through SIGHASH_ALL. Multisig uses an empty leading witness element and signatures in public-key order. Relative time locks use 512-second units. Node finality and input-age checks still apply.

**Public activation is not scheduled.** These validation rules are implemented and available to disposable regtest through the explicit `Chain(..., spending_activation=height)` setting. The activation configuration is persisted and cannot change silently on reopening. A public node refuses a locally chosen activation height. Do not fund a new template on the public network before coordinated activation. `decodescript` alone does not make a script spendable. Existing P2WPKH and activated HTLC behavior remain supported.

```powershell
python -m unittest tests.test_fee_policy_v43 tests.test_spending_v43 tests.test_node_contract -v
python -m sumuww --network regtest --database isolated.sqlite wallet-send --wallet test-wallet.json --to-address drt1... --amount 1 --fee-mode normal
# Alternatively choose --fee-rate 2.5 (yugeon/vB). Legacy --fee is a total in SMW.
```

The tests use public fixture keys and disposable databases. They cover replacement descendants, rollback, concurrent writers, reorganization, signature thresholds, activation boundaries and output locks. No production wallet or funds are used.


## Replacement history and script inspection

Wallet history retains the selected script's locally observed replacement records across restart, including descendants removed when a parent is replaced. These rows are historical information and never enter balance calculations. A current mempool or active-chain transaction takes precedence over an older replacement record, including after a reorganization. The node stores public script hashes and integer net amounts in the same atomic write as the replacement. It stores no keys or signatures in this history. The history is limited to 1,000 replacement events and 4,000,000 bytes of amount summaries; older records can expire. Records from earlier versions without amount summaries are not reconstructed. This is local history, not a network-wide archive. A descendant is labelled as removed after its parent was replaced, not as a successful payment.

Explorer displays a spending template only when the revealed witness script matches the previous output's P2WSH hash and has the canonical supported form. This is decoding, not signature validation or an assertion of spendability. Unrevealed output conditions are not inferred from a script hash. Public multisig and output-lock activation remains unscheduled.


## Block reward breakdown

The history and API expose each block's new-issuance reward, transaction-fee reward and claimed total. These are block totals, not an allocation to an individual address. A wallet's received amount remains separate. Amounts use integer yugeon and eight-decimal SMW strings. History, balances and spending rules are unchanged.

The node computes transaction fees from validated inputs minus outputs. A derived fee index is committed atomically with a newly accepted block. Existing active-chain records are rebuilt during verified startup replay. This does not modify block bytes, transaction IDs, balances or consensus. Reorganizations select the replacement branch's records. A legacy read-only database without fee information reports unknown values, never an invented zero.

`getblock` and `getblocktemplate` include `reward`; a confirmed coinbase returned by `getrawtransaction` includes `mining_reward`. The object has `scope="block"`, `amount_unit="yugeon"`, `allocation` and paired `_units`/`_smw` fields: `subsidy_reward`, `fee_reward`, `claimed_reward`, `subsidy_limit`, `transaction_fees`, `unclaimed_reward`. A fully claimed reward has `allocation="full"`. For an underclaim, the paid split is unspecified: both component rewards are null, with the limits, fees, total and unclaimed amount available separately. Genesis is marked `genesis_unspendable`. Missing fee data is marked `unavailable`. Zero issuance after the subsidy schedule ends remains distinct from unknown data: a fully claimed fee-only reward reports an issuance reward of zero.

Explorer calculates the same block breakdown from its indexed public transaction inputs and outputs. It reads the node database without modifying it. Mining statistics remain an aggregate view; individual block and mining-transaction details provide the breakdown.
