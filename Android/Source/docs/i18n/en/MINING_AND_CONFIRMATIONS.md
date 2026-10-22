# SUMUWW Mining Modifications and Transaction Confirmations

## Why faster computation is allowed

Faster implementations of the same calculation must still meet expected difficulty and reward rules. PoW checks whether the submitted hash satisfies the required target. It does not require proof of the time spent, equipment used or optimizations applied, so faster valid calculation is allowed. Increased speed grants no arbitrary easier nBits or extra reward. Rewards from valid optimization can be transferred to ordinary wallets after maturity.

## Lowered difficulty or increased rewards

Normal nodes reject arbitrarily reduced difficulty, excess rewards, nonexistent inputs and invalid signatures. Invalid block outputs do not exist in the normal active ledger, and sending them to an ordinary wallet does not make them valid coins. Signatures prove ownership of existing outputs; they do not authorize issuance of valid outputs from invalid ones.

## Transactions and UTXOs

The ledger records unspent transaction outputs, or UTXOs. Transactions consume existing outputs and create new ones. Nodes check input existence, duplicates, maturity, owner signatures and amount totals to reject double spending and overspending. The basic spending format is native P2WPKH with `SIGHASH_ALL`.

## A private chain that follows normal rules

A rule-compliant private chain with greater cumulative work can change transaction history. Offline creation alone does not make a block invalid; nodes judge it by the same consensus rules. Confirmations do not guarantee irreversible finality. Proof-of-work security depends on honest mining work and independent node validation, and does not guarantee immunity to majority-hashrate attacks.
