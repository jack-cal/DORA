# SUMUWW Android 0.6.95 · Release notes

SUMUWW Android 0.6.95 · The node validates, stores, relays and exposes chain data.

The API specification describes the embedded node core. The Android app has no RPC configuration screen.

## RPC and HTTP API

validateaddress checks the checksum and selected network. decoderawtransaction returns decoded_only, not signature validity or confirmation. Existing OP_RETURN outputs preserve data for external programs. The node adds fee queries, submission checks, RBF replacement status and ordered block data records. Replacements are validated before any pending transaction is removed. Multisig and output locks are implemented for isolated activation tests; they are not yet active on the public network.

[API_CONTRACT.json](../../../API_CONTRACT.json)
