# SUMUWW Android 0.6.95 · Verification

SUMUWW Android 0.6.95 · The node validates, stores, relays and exposes chain data.

The API specification describes the embedded node core. The Android app has no RPC configuration screen.

## RPC and HTTP API

validateaddress checks the checksum and selected network. decoderawtransaction returns decoded_only, not signature validity or confirmation. Existing OP_RETURN outputs preserve data for external programs. The node adds fee queries, submission checks, RBF replacement status and ordered block data records. Replacements are validated before any pending transaction is removed. Multisig and output locks are implemented for isolated activation tests; they are not yet active on the public network.

## Transaction and block lookup

`getrawtransaction` searches the active chain and mempool, not orphan-only transactions. Inputs identify outpoints, not a unique sender address. `getblock` takes Boolean `verbose`; inactive stored blocks have `active=false` and `confirmations=-1`. Their raw transactions remain available by block hash. `findspendingtransaction` searches confirmed active-chain spends only; null does not prove availability. Check `gettxout` with `include_mempool=true`. All confirmations and active flags can change after a reorganization.

[API_CONTRACT.json](../../../API_CONTRACT.json)
