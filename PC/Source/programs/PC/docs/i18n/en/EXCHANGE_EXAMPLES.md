# SUMUWW · Verification

SUMUWW PC 0.57.46 · The node validates, stores, relays and exposes chain data.

## Signing format

The optional source SDK assembles transactions and checks supplied signatures without keys or network access. It is not a signer or node command. Its P2WPKH payment restriction applies to the example format, not the node. The existing personal wallet remains available.

## Verification

Run python examples/node_contract.py from source with dependencies installed. Public fixture keys and disposable regtest test submission, rejection, confirmations, reorganization and data persistence. No real funds, user profile or hardware signer is used.

```powershell
python examples/node_contract.py
python -m unittest tests.test_node_contract tests.test_rpc -v
```

[Documentation](README.html) · [Node interface](EXCHANGE_INTEGRATION.html) · [RPC and HTTP API](RPC_API.html) · [Node operation](NETWORK_RUNBOOK.html) · [Release notes](RELEASE_NOTES.html)

[Extended English reference](../../../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../../../API_CONTRACT.json) · [vectors.json](../../../../../examples/exchange/vectors.json)
