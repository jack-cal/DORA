# SUMUWW node features · PC 0.57.46

1 SMW = 100,000,000 yugeon. Automatic fees offer slow, normal and fast presets based on local observations; they do not guarantee confirmation times. You can enter a rate in yugeon/vB manually. Review the final fee and total in SMW before sending. A rejected transaction does not debit your balance.

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
