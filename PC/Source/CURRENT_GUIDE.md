# SUMUWW PC 0.57.46

1 yugeon = 0.00000001 SMW. Wallet fees support slow, normal and fast suggestions or a manual yugeon/vB rate, with the exact total shown before confirmation. The node adds signed-transaction preflight, bounded atomic replacement and block data record queries.

Multisig and output-lock validation is implemented for explicitly activated isolated test chains; public activation is not scheduled.

[Node features](NODE_FEATURES.html) · [API](EXCHANGE_INTEGRATION.html) · [34 language editions](docs/index.html).

Automatic fees use current pending volume, block capacity and transaction priority. Past block fees are not used. A quiet queue keeps the minimum rate. The preview refreshes; the final confirmation fixes the fee. Observations cover the connected local node, not every node.
