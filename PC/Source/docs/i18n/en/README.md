# SUMUWW · Documentation

SUMUWW PC 0.57.46 · The node validates, stores, relays and exposes chain data.

## Signing format

The optional source SDK assembles transactions and checks supplied signatures without keys or network access. It is not a signer or node command. Its P2WPKH payment restriction applies to the example format, not the node. The existing personal wallet remains available.

## RPC and HTTP API

validateaddress checks the checksum and selected network. decoderawtransaction returns decoded_only, not signature validity or confirmation. Existing OP_RETURN outputs preserve data for external programs. The node adds fee queries, submission checks, RBF replacement status and ordered block data records. Replacements are validated before any pending transaction is removed. Multisig and output locks are implemented for isolated activation tests; they are not yet active on the public network.

## Verification

Run python examples/node_contract.py from source with dependencies installed. Public fixture keys and disposable regtest test submission, rejection, confirmations, reorganization and data persistence. No real funds, user profile or hardware signer is used.

```text
network: sumuww (dora)
genesis: 00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97
HRP: sumuww
P2P magic: d052470c
1 SMW = 100000000 yugeon
```

[Node interface](EXCHANGE_INTEGRATION.html) · [RPC and HTTP API](RPC_API.html) · [Node operation](NETWORK_RUNBOOK.html) · [Release notes](RELEASE_NOTES.html) · [Verification](EXCHANGE_EXAMPLES.html)

[Extended English reference](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
