# SUMUWW PC 0.57.23 RPC and HTTP API

SUMUWW PC program · 0.57.23

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
import json
import urllib.request
rpc_host = input("Numeric RPC loopback address: ").strip()
from pathlib import Path

token = Path("data/server/rpc-token").read_text(encoding="utf-8").strip()
payload = {"jsonrpc": "2.0", "id": 1, "method": "getblockchaininfo", "params": {}}
request = urllib.request.Request(
    f"http://{rpc_host}:18443/rpc",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
)
with urllib.request.urlopen(request, timeout=10) as response:
    print(json.load(response))
```

## Methods and parameters

getmempoolinfo and GET /api/v1/mempool/info return one consistent read snapshot. Integer fields are size, bytes, max_transactions, max_bytes, remaining_transactions and remaining_bytes; full is Boolean. This version has 15 RPC methods and 11 REST routes.

MempoolFull is temporary local-capacity rejection: JSON-RPC -32005 and HTTP 503. The rejected transaction is not queued or accepted. Retry when capacity becomes available; this does not guarantee confirmation.

| Method | Parameters | Result / action |
|---|---|---|
| `help` | `{} / []` | Available methods and parameter information |
| `getblockchaininfo, getnetworkinfo` | `{} / []` | Validated active-chain state / peer connection and synchronization state |
| `getblockcount, getbestblockhash` | `{} / []` | Active height / active tip display hash |
| `getblockhash` | `height` | Active block hash at height |
| `getblock` | `hash, verbose=true` | Block details; `verbose=false` returns serialized block hex |
| `gethtlcinfo` | `{} / []` | HTLC configuration and current/next-block activation; public height 9100 |
| `gettxout` | `txid, index, include_mempool=true` | Confirmed unspent output or null; optionally exclude mempool-spent outputs |
| `findspendingtransaction` | `txid, index, start_height=0` | Spending transaction in the active chain, including raw hex, or null |
| `getrawmempool` | `{} / []` | Current mempool transaction IDs |
| `getmempoolinfo` | `{} / []` | Local capacity and remaining space from one read snapshot |
| `getrawtransaction` | `txid, verbose=true` | Transaction in active chain or mempool; `verbose=false` returns hex |
| `listunspent` | `address, limit=100, offset=0` | Address UTXOs with pending-spent and spendable flags; paginated |
| `getaddressbalance` | `address` | Address balance on the current active chain |
| `sendrawtransaction` | `hex` | Validate signed transaction bytes; returns `txid` and `accepted` |
| `submitblock` | `hex` | Validate block bytes; returns `hash`, `accepted`, `already_known`, `activated` |
| `getblocktemplate` | `address` | Construct a candidate; no CPU mining in the HTTP service |

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

Money fields ending in `_units` are integer minimum units. Fields ending in `_sumuww` are fixed 8-decimal strings; do not parse or sign using binary floating-point amounts. 1 SMW is `100000000` units. Confirmations follow the current active chain and can change after a valid reorganization. Coinbase outputs may be spent only when spending height minus creation height is at least 100. Balance/UTXO spendability is assessed for the next block and excludes inputs reserved by pending transactions. Addresses do not grant spending authority. External callers must produce signed transaction bytes with the existing wallet CLI or their own compatible signer before submission.

Fees equal total inputs minus total outputs. The GUI and wallet-send CLI now use automatic estimation by default; the sender may override it with any nonnegative manual total, including 0. The sender pays the fee in addition to the payment; the recipient receives the full specified amount. Included fees may be claimed by the block miner at the block reward address with the subsidy. There is no developer share, automatic burn or additional issuance. A higher fee can improve the chance of inclusion when blocks are congested, but does not change the target block interval or guarantee faster propagation or confirmation.

## Limits and errors

The server limits request bodies to `8004096` bytes, headers to `8192` bytes, batches to 16 calls, concurrent requests to 16 and a request deadline to 10 seconds. `limit` is 1–1000; `offset` is 0–1000000. HTTP Host must be numeric loopback and match the actual port. Authentication precedes execution. Unsupported routes, invalid JSON, wrong parameter types and malformed or invalid transaction/block data are rejected. A `getblocktemplate` request for `sumuww` requires a connected, fully synchronized peer; offline regtest is permitted. Templates provide `height`, `previousblockhash`, `bits`, `target`, `header_hex` and `block_hex`. Miners must satisfy normal PoW and all block rules before submitting; this endpoint neither lowers difficulty nor issues coins by itself.

JSON-RPC errors: `-32700` parse error, `-32600` invalid request, `-32601` unknown method, `-32602` invalid parameters, `-32603` internal error, `-32001` not found, `-32002` validation failure, `-32003` not running/mining gate, `-32004` batch response limit. A successful submission is not an irreversible confirmation or guaranteed active-chain inclusion. Read the returned state and current chain confirmations.

## License and consensus

SUMUWW's own code is distributed under the MIT license, the same license type used by Bitcoin Core. Use, copying, modification, merging, publication, distribution, sublicensing, sale and commercial use are permitted. Copies or substantial portions must retain the copyright and permission notice. The software is supplied without warranty; MIT does not require publishing modified source or paying royalties. External dependencies retain their own license notices. The English LICENSE text is authoritative. `Copyright (c) 2026 SUMUWW contributors`. [MIT](../../../LICENSE).

UI, API and performance improvements can preserve genesis, issuance, difficulty, signatures, UTXO validity and cumulative-work chain selection. Each node still validates independently; neither the author nor an API caller can force upgrades or mint, freeze or rewrite balances. Adoption of changed consensus rules is voluntary and may split the chain. These rules do not cryptographically prevent people from creating a fork. SUMUWW has a decentralized consensus architecture; sustained participation by independent public operators has not yet been established by the local checks.

## Fee policy

The default GUI estimates the fee and shows the recipient, payment, fee and total debit for confirmation. Advanced settings allow a manual fee. The wallet-send CLI uses automatic estimation when `--fee` is omitted or set to `--fee auto`; `--fee 0` explicitly requests a zero manual fee. Automatic estimation is a wallet policy, not a mandatory network fee or a change to consensus. The CLI treats running wallet-send as authorization to submit directly and reports the actual fee, total debit, fee mode and estimate source; its command does not open the GUI confirmation step.

The local estimator uses positive transaction fee-rate samples from the most recent 20 active-chain blocks and the node’s pending transactions. Virtual size is `ceil(weight/4)`; the upper quartile of observed fee per virtual byte determines the estimate. Payment sizing conservatively budgets a 73-byte DER signature, a 33-byte public key and 2 outputs per supported wallet payment. With no positive sample, the fallback total is `0.001 SMW`. Automatic total fees are capped at `0.01 SMW`; a sender’s explicit manual fee may exceed that cap. This cap may make the automatic offer insufficient during congestion. This is a simple local estimate, not Bitcoin Core’s confirmation predictor or a promised speed. The active-chain history is limited to its latest 1000 transaction samples. The upper quartile uses the nearest-rank 75th percentile and at least 1 smallest unit per virtual byte; the resulting total is rounded upward.

The GUI displays a prepared payment quote and submits that same payment after approval, without silently changing the fee. A quote expires after 120 seconds; locking the wallet or changing the wallet or network invalidates it. Changed inputs or chain conditions can require preparing and confirming again. Final submission revalidates the transaction against current UTXOs and maturity.

The default miner ranks transactions by ancestor-package fee per virtual byte: unconfirmed parents are counted together with their child, parents are placed first, equal-rate packages preserve arrival order, and real block weight and signature-operation limits are enforced. Zero-fee valid transactions remain eligible. Inclusion depends on the chosen miner, available block space and current chain. RPC/API provides 15 methods and 11 REST routes; it adds no RPC fee-estimation method in this release.
