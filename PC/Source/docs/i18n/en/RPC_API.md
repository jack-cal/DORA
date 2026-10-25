# SUMUWW · RPC and HTTP API

SUMUWW PC 0.57.46 · The node validates, stores, relays and exposes chain data.

## RPC and HTTP API

validateaddress checks the checksum and selected network. decoderawtransaction returns decoded_only, not signature validity or confirmation. Existing OP_RETURN outputs preserve data for external programs. The node adds fee queries, submission checks, RBF replacement status and ordered block data records. Replacements are validated before any pending transaction is removed. Multisig and output locks are implemented for isolated activation tests; they are not yet active on the public network.

## Authentication and limits

Enable RPC explicitly at numeric loopback `127.0.0.1:18443` with its private Bearer token. No wallet unlock or remote signing is exposed. Use a local service or authenticated tunnel; browser Origin/Referer requests are rejected. JSON-RPC uses POST `/rpc`, an object/array `params` and an `id`; notifications return HTTP 204. Limits: body 8004096 bytes, headers 8192 bytes, batch 16, concurrent requests 16, deadline 10 seconds; pagination limit 1–1000 and offset 0–1000000. There are 28 methods and 11 REST routes.

## Amounts and available outputs

`_units` means integer smallest units; `_smw` is an 8-decimal string; `_dora` is a compatibility alias. There is no `_sumuww` amount field. 1 SMW = 100000000 units. `gettxout` has no `spendable` field and may return immature coinbase outputs. Coinbase needs at least 100 confirmations for spending in the next block. Filter `listunspent` by `spendable`; available amounts from `getaddressbalance` exclude immature and pending-spent funds. New mempool outputs are not confirmed funds. Check the tip across pages and revalidate selected inputs.

1 SMW = 100,000,000 yugeon. Automatic fees offer slow, normal and fast presets based on local observations; they do not guarantee confirmation times. You can enter a rate in yugeon/vB manually. Review the final fee and total in SMW before sending. A rejected transaction does not debit your balance.

`1 yugeon = 0.00000001 SMW` · `1 SMW = 100000000 yugeon`

| API / wallet | yugeon / SMW |
|---|---|
| minimum relay | 1 yugeon/vB |
| automatic cap | 0.01 SMW |
| manual cap | 1 SMW |
| manual rate | 1–100000 yugeon/vB |

Automatic fees use current pending volume, block capacity and transaction priority. Past block fees are not used. A quiet queue keeps the minimum rate. The preview refreshes; the final confirmation fixes the fee. Observations cover the connected local node, not every node.

Wallet history retains local replacement records after restart. Removed transactions do not affect the balance.

Mining history separates new issuance, transaction fees and total reward for each block. Your received amount is shown separately. A partial claim does not identify how the two components were divided. The node provides 28 RPC methods, including fee estimation, and validates and relays signed transactions.

## Transaction and block lookup

`getrawtransaction` searches the active chain and mempool, not orphan-only transactions. Inputs identify outpoints, not a unique sender address. `getblock` takes Boolean `verbose`; inactive stored blocks have `active=false` and `confirmations=-1`. Their raw transactions remain available by block hash. `findspendingtransaction` searches confirmed active-chain spends only; null does not prove availability. Check `gettxout` with `include_mempool=true`. All confirmations and active flags can change after a reorganization.

| method | params |
|---|---|
| `getblockchaininfo` | `{} / []` |
| `gethtlcinfo` | `{} / []` |
| `getspendinginfo` | `{} / []` |
| `getdatarecords` | `blockhash, offset=0, limit=100` |
| `decodescript` | `hex` |
| `gettxout` | `txid, index, include_mempool=true` |
| `findspendingtransaction` | `txid, index, start_height=0` |
| `getnetworkinfo` | `{} / []` |
| `getblockcount` | `{} / []` |
| `getbestblockhash` | `{} / []` |
| `getblockhash` | `height` |
| `getblock` | `hash, verbose=true` |
| `getrawmempool` | `{} / []` |
| `getmempoolinfo` | `{} / []` |
| `getmempoolpolicy` | `{} / []` |
| `estimatefee` | `vsize=140, mode=normal` |
| `testmempoolaccept` | `hex` |
| `getmempoolentry` | `txid` |
| `gettransactionstatus` | `txid` |
| `getrawtransaction` | `txid, verbose=true` |
| `decoderawtransaction` | `hex` |
| `validateaddress` | `address` |
| `listunspent` | `address, limit=100, offset=0` |
| `getaddressbalance` | `address` |
| `sendrawtransaction` | `hex` |
| `submitblock` | `hex` |
| `getblocktemplate` | `address` |
| `help` | `{} / []` |

| HTTP | URI | JSON |
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

[Documentation](README.html) · [Node interface](EXCHANGE_INTEGRATION.html) · [Node operation](NETWORK_RUNBOOK.html) · [Release notes](RELEASE_NOTES.html) · [Verification](EXCHANGE_EXAMPLES.html)

[Extended English reference](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
