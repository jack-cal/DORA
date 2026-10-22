# SUMUWW Basic Rules: Comparison Baseline

<!-- current-links-9000 -->
## 2026-10-22 · 9000 · 20% · DGW/10

Valid blocks through 8999 remain usable, including those sent together with an invalid later suffix. From 9000, every block needs a producer commitment. DGW uses 24 preceding blocks and recalculates at 9000, 9010, 9020…; intervening blocks keep the parent difficulty. The target interval remains 600 seconds. Connection events are random with probability 20%. Three discovered identities sign after PoW; mining and block acceptance do not wait for signatures. Cumulative work takes priority; valid, nonconflicting connections break work ties, followed by the smaller tip hash. Late evidence can change a tie. See the exact implementation and limitations below.

[Current protocol / exact format / limitations](../../../CONNECTION_PROOFS_9000.html)
<!-- /current-links-9000 -->


| Basic item | SUMUWW choice and comparison material |
|---|---|
| Issuance | First 150,000 blocks: 50 SMW; at height 150,000: 25 SMW; thereafter integer halving every 210,000 blocks. [vectors](../../pc043/vectors/consensus_vectors.json) |
| Genesis | Own anchor; genesis UTXO excluded; no copying BTC history or balances |
| Amounts and transactions | Integer, duplicate/missing input, output-limit, and fee checks. [tx_check.cpp](https://github.com/bitcoin/bitcoin/blob/f490f5562d4b20857ef8d042c050763795fd43da/src/consensus/tx_check.cpp) |
| Signatures | Basic spending uses native P2WPKH / SIGHASH_ALL. [BIP143](https://github.com/bitcoin/bips/blob/master/bip-0143.mediawiki) |
| Coinbase | Height prefix and maturity 100. [BIP34](https://github.com/bitcoin/bips/blob/master/bip-0034.mediawiki) |
| PoW and difficulty | Valid blocks through 8999 remain usable, including those sent together with an invalid later suffix. From 9000, every block needs a producer commitment. DGW uses 24 preceding blocks and recalculates at 9000, 9010, 9020…; intervening blocks keep the parent difficulty. The target interval remains 600 seconds. Connection events are random with probability 20%. Three discovered identities sign after PoW; mining and block acceptance do not wait for signatures. Cumulative work takes priority; valid, nonconflicting connections break work ties, followed by the smaller tip hash. Late evidence can change a tie. See the exact implementation and limitations below. [DGW v3](https://github.com/dashpay/dash/blob/728f5055836c6d29806412fc7223ac8fe05af991/src/pow.cpp) |
| Work | Work derived from target and valid cumulative work. [chain.cpp](https://github.com/bitcoin/bitcoin/blob/f490f5562d4b20857ef8d042c050763795fd43da/src/chain.cpp) |
| Addresses | Default SUMUWW HRP sumuww; test networks drt and dtl; witness-v0/20 bytes Bech32. [BIP173](https://github.com/bitcoin/bips/blob/master/bip-0173.mediawiki) |
