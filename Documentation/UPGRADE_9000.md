# SUMUWW height-9,000 compatibility notice

## Upgrade before block 9,000

The upgraded consensus rules apply at height **9,000 inclusive**. Blocks produced by legacy software under the old, pre-upgrade rules at height 9,000 or above are rejected by upgraded nodes and cannot extend the upgraded chain. Continued mining on a legacy branch does not make those blocks acceptable.

Valid historical blocks through **8,999 remain usable**, including the valid prefix of a mixed synchronization batch whose later legacy continuation is invalid. Existing wallets, coins, valid history, issuance and halvings are preserved. Update both miners and validating nodes before activation. This is validation by block rules, not a blanket rejection based only on an advertised software version.
