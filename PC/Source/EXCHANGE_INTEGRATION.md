# SUMUWW node integration — PC 0.57.46

English is the default. The current node contract, API corrections and test guidance are available in all 34 interface languages. 

## Node capabilities

SUMUWW provides independent full-chain validation, peer synchronization, authenticated queries, signed-transaction validation and submission, address and signature specifications, source references and disposable tests. The personal wallet, mining and connection-proof features remain available.

## Network and address specification

Public selector: `sumuww`; internal alias: `dora`. Genesis: `00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97`. P2P magic: `d052470c`. Public address HRP: `sumuww`. 1 SMW = 100000000 yugeon. Native receiving addresses use witness-v0 P2WPKH: HASH160 of a compressed secp256k1 public key. No mandatory memo/tag. Check network and genesis; no Bitcoin derivation-path assumption is warranted.

## Node API

Enable local RPC explicitly. It uses numeric IPv4 loopback and a private Bearer token. The existing PC GUI and headless peer command can configure it. 

```powershell
.\SUMUWW-node.exe peer --database data/server/node.sqlite --network sumuww --listen 0.0.0.0:18444 --allow-internet --rpc --rpc-port 18443 --rpc-token-file data/server/rpc-token
.\SUMUWW-node.exe rpc --token-file data/server/rpc-token getblockchaininfo
```

There are 28 RPC methods and 11 REST routes. See [API contract](API_CONTRACT.json), [full API reference](programs/PC/docs/RPC_API.html), and [all language editions](docs/index.html). No RPC accepts wallet secrets. `validateaddress` checks network and checksum, not ownership. `decoderawtransaction` parses bytes and returns `validation=decoded_only`; it never implies valid signatures, acceptance or confirmations. `sendrawtransaction` validates signed bytes against current node state and queues accepted transactions for peer relay. A valid request does not guarantee peer delivery or mining.

```json
{"jsonrpc":"2.0","id":1,"method":"validateaddress","params":{"address":"<address-on-selected-network>"}}
```

```json
{"jsonrpc":"2.0","id":2,"method":"decoderawtransaction","params":{"hex":"<serialized-transaction-hex>"}}
```

## Source reference for external signing

The optional `sdk/sumuww_integration/transactions.py` belongs to the source archive, not the frozen node or Android runtime. It assembles explicit previous outputs and payment outputs, exposes signing digests, verifies externally supplied signatures and serializes the completed transaction. It reads no keys, files, network or node database.

The reference format is `sumuww-external-signing-v1`, not PSBT. Its P2WPKH-only payment restriction applies to that example format; it is not an extra node consensus restriction. The node independently accepts supported transactions, including its activated exact HTLC and data outputs. External developers can implement the serialization/signature specification directly.

```python
# From the PC source root, with sdk on the module search path:
from sumuww_integration.transactions import create_package, inspect_package, attach_signatures, finalize_package
# Supply explicitly selected (previous_transaction_hex, output_index) pairs.
package = create_package(network, previous_outputs, payments, change_address, fee_units=fee)
view = inspect_package(package, network)
# Your separate signer signs each digest_hex; this SDK never signs or holds keys.
signed = attach_signatures(package, network, externally_supplied_signatures)
raw_hex = finalize_package(signed, network).serialize().hex()
```

An external signer signs each exact 32-byte `digest_hex` with secp256k1 ECDSA, without hashing again. Supply a compressed 33-byte public key and strict DER signature without the sighash suffix. Attachment adds SIGHASH_ALL (`01`) and verifies every supplied signature. The signing digest is BIP143-style with input value and script. A finalized native P2WPKH witness has the signature-plus-suffix and public key.

Reference fields: `format`, `network`, `genesis_hash`, `unsigned_tx`, `previous_transactions`, `request_id`, `signatures`. The request ID hashes the first five fields as sorted ASCII-escaped JSON, separators comma and colon, prefixed by ASCII `SUMUWW signing request v1` followed by one zero byte, using SHA-256. Signatures are excluded. Previous transaction bytes bind amounts/scripts to txids but do not prove current unspent status. Metadata does not change consensus replay rules. V1 requires transaction version 2, final sequences, locktime 0, 1–1000 explicitly selected inputs, positive P2WPKH payments and a package under 16 MB. These are reference-format limits. Fees are input sum minus output sum in integer units. The reference accepts a fixed fee or integer units/vbyte; it offers no automatic fund collection.

[Deterministic public test vectors](examples/exchange/vectors.json) include request IDs, digests, supplied signatures and exact signed hex. No real key material appears in these fixtures.

## Confirmation and reorganization contract

Use output indices and actual scripts/amounts when reading transfers. `getrawtransaction` searches active-chain transactions and the mempool. Pending transactions have 0 confirmations and `in_mempool=true`; confirmed transactions include `height` and `blockhash`. Missing or orphan-only results return -32001. `getblock` retains raw bytes of stored inactive blocks with `active=false` and `confirmations=-1`. `getblockhash(height)` gives the currently active block. Multiple calls can span a tip change; compare tips and re-query when needed. Confirmation counts may change after a reorganization.

`sendrawtransaction` rejects duplicate submissions with -32002. After timeout, the caller can query the known txid and retry the same bytes; the node does not turn a retry into a new payment. `gettxout` may return immature coinbase outputs; maturity requires at least 100 confirmations for spending in the next block. `listunspent` exposes `spendable`.

## Transaction data

OP_RETURN outputs preserve raw bytes in transactions and blocks and are excluded from spendable UTXOs. The node exposes ordered block transactions, active-block hashes and reorganization state. Native spending supports P2WPKH and the activated exact HTLC contract. Transaction/block size and weight limits continue to apply. This release does not change consensus or script rules.

## Reproducible node tests

Install the source dependencies; run from the PC source root:

```powershell
python examples/node_contract.py
python -m unittest tests.test_node_contract tests.test_rpc -v
```

The fixture always creates temporary regtest data and uses public test keys. It tests authenticated HTTP address/decoding queries, unsigned and invalid-signature rejection, valid external signed submission, duplicate and double-spend rejection, active confirmations, greater-work reorganization, reconfirmation, OP_RETURN lookup/persistence, and rejection of unsupported RPC methods. The fixture measures disposable local behavior; public-network availability and hardware signing are outside its scope.

## Operation and recovery

Extract the complete desktop package and retain its `_internal` folder. Preserve encrypted wallets, recovery material, data directories and saved language preferences. Verify genesis, peer connections and synchronization; stop normally before maintenance. For chain recovery use a separate directory and resynchronize, never overwrite a live database.


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
