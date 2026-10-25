# SUMUWW · Node operation

SUMUWW PC 0.57.46 · The node validates, stores, relays and exposes chain data.

## Network and addresses

The public network is `sumuww`; `dora` is its internal alias. Check the genesis hash below. Native addresses use witness v0 P2WPKH and HASH160 of a compressed secp256k1 public key. There is no mandatory memo or tag. Reject wrong-network addresses and invalid checksums. Record each HD receive/change branch and index; do not assume Bitcoin's derivation path.

## Authentication and limits

Enable RPC explicitly at numeric loopback `127.0.0.1:18443` with its private Bearer token. No wallet unlock or remote signing is exposed. Use a local service or authenticated tunnel; browser Origin/Referer requests are rejected. JSON-RPC uses POST `/rpc`, an object/array `params` and an `id`; notifications return HTTP 204. Limits: body 8004096 bytes, headers 8192 bytes, batch 16, concurrent requests 16, deadline 10 seconds; pagination limit 1–1000 and offset 0–1000000. There are 28 methods and 11 REST routes.

## Transaction and block lookup

`getrawtransaction` searches the active chain and mempool, not orphan-only transactions. Inputs identify outpoints, not a unique sender address. `getblock` takes Boolean `verbose`; inactive stored blocks have `active=false` and `confirmations=-1`. Their raw transactions remain available by block hash. `findspendingtransaction` searches confirmed active-chain spends only; null does not prove availability. Check `gettxout` with `include_mempool=true`. All confirmations and active flags can change after a reorganization.

## Verification

Run python examples/node_contract.py from source with dependencies installed. Public fixture keys and disposable regtest test submission, rejection, confirmations, reorganization and data persistence. No real funds, user profile or hardware signer is used.

```text
network: sumuww (dora)
genesis: 00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97
HRP: sumuww
P2P magic: d052470c
1 SMW = 100000000 yugeon
```

[Documentation](README.html) · [Node interface](EXCHANGE_INTEGRATION.html) · [RPC and HTTP API](RPC_API.html) · [Release notes](RELEASE_NOTES.html) · [Verification](EXCHANGE_EXAMPLES.html)

[Extended English reference](../../../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../../../API_CONTRACT.json) · [vectors.json](../../../../../examples/exchange/vectors.json)
