# SUMUWW PC 0.57.46

This release adds address validation and transaction decoding to the node API. The node provides signed-transaction validation and submission, block/transaction/UTXO queries, synchronization state and reorganization information. Existing wallet, mining and connection-proof features are retained. English is the default, with documentation in all 34 supported languages.

See [node interface](../../EXCHANGE_INTEGRATION.html) and [language editions](../../docs/index.html).

The optional source reference provides key-free transaction assembly, digest inspection, signature attachment and serialization. The disposable regtest example checks validation, confirmations, reorganization and data persistence. The compiled program uses the existing node, wallet and RPC commands.

1 SMW = 100,000,000 yugeon. Automatic fees offer slow, normal and fast presets based on local observations; they do not guarantee confirmation times. You can enter a rate in yugeon/vB manually. Review the final fee and total in SMW before sending. A rejected transaction does not debit your balance.

The node adds fee queries, submission checks, RBF replacement status and ordered block data records. Replacements are validated before any pending transaction is removed. Multisig and output locks are implemented for isolated activation tests; they are not yet active on the public network.
