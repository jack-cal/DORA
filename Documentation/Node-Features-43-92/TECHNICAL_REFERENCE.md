# SUMUWW node features · PC 0.57.43

1 SMW = 100,000,000 yugeon. Automatic fees offer slow, normal and fast presets based on local observations; they do not guarantee confirmation times. You can enter a rate in yugeon/vB manually. Review the final fee and total in SMW before sending. A rejected transaction does not debit your balance.

## Yugeon, fee policy and transaction replacement

1 SMW = 100,000,000 yugeon; one yugeon is 0.00000001 SMW. Existing `_units` integer fields are yugeon. Serialization and balances are unchanged. A vB measures transaction data, not currency: `ceil(weight / 4)`. Fee rates are shown as yugeon/vB; policy API rates use yugeon per 1,000 vB.

The public node's default relay floor is 1 yugeon/vB. Regtest defaults to zero for controlled tests. This is local admission policy, not block consensus: a valid zero-fee transaction in a block remains valid. Refusal does not debit confirmed funds. An unconfirmed transaction can reserve local wallet inputs until it is confirmed or removed.

Automatic suggestions sample positive fees in the last 20 active blocks (up to 1,000 observations) and the local mempool. Slow, normal and fast use the 25th, 75th and 95th percentiles. Without samples the starting rate is 1 yugeon/vB. Rates round upward to 0.001 yugeon/vB; total fees round upward to whole yugeon. These presets do not promise confirmation times. Automatic total fees are capped at 0.01 SMW; the quote fails if this cannot meet the local relay floor. A manual wallet rate is 1–100,000 yugeon/vB with at most three decimals; the total wallet fee limit is 1 SMW. These caps do not constrain externally signed transactions or block validity.

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
