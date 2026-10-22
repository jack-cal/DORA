# SUMUWW Basic Rules: Comparison Baseline

| Basic item | SUMUWW choice and comparison material |
|---|---|
| Issuance | First 150,000 blocks: 50 SMW; at height 150,000: 25 SMW; thereafter integer halving every 210,000 blocks. [vectors](../vectors/consensus_vectors.json) |
| Genesis | Own anchor; genesis UTXO excluded; no copying BTC history or balances |
| Amounts and transactions | Integer, duplicate/missing input, output-limit, and fee checks. [tx_check.cpp](https://github.com/bitcoin/bitcoin/blob/f490f5562d4b20857ef8d042c050763795fd43da/src/consensus/tx_check.cpp) |
| Signatures | Basic spending uses native P2WPKH / SIGHASH_ALL. [BIP143](https://github.com/bitcoin/bips/blob/master/bip-0143.mediawiki) |
| Coinbase | Height prefix and maturity 100. [BIP34](https://github.com/bitcoin/bips/blob/master/bip-0034.mediawiki) |
| PoW and difficulty | SHA-256d proof of work and valid block contents are required. The target average block interval is 600 seconds. Below height 8,064, the previous 2,016-block adjustment rules remain in force. From height 8,064, DGW v3 recalculates difficulty for every block using the 24 preceding blocks on the same parent branch. Actual block intervals vary. [DGW v3](https://github.com/dashpay/dash/blob/728f5055836c6d29806412fc7223ac8fe05af991/src/pow.cpp) |
| Work | Work derived from target and valid cumulative work. [chain.cpp](https://github.com/bitcoin/bitcoin/blob/f490f5562d4b20857ef8d042c050763795fd43da/src/chain.cpp) |
| Addresses | Default SUMUWW HRP sumuww; test networks drt and dtl; witness-v0/20 bytes Bech32. [BIP173](https://github.com/bitcoin/bips/blob/master/bip-0173.mediawiki) |
