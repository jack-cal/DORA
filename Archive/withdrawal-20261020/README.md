# SUMUWW (SMW) — affected releases withdrawn

The Windows node, Android node and standalone wallet releases that implement or validate the height-9000 block-signature rule have been withdrawn. Their published behavior did not match the intended signing sequence. In the released node code, the final signers are discovered and their signatures are collected **after** a valid PoW block is found. The intended preparation and delivery during mining, with registration complete when the block is created, was not implemented or verified.

**There is no verified replacement release.** Do not use the withdrawn builds for mining, chain validation or transfers. Earlier builds predate the height-9000 rule and are historical records, not compatible replacements for a chain using that rule. Preserve existing encrypted wallets, recovery material and node data; do not uninstall an Android app or clear its data merely because a release was withdrawn.

The [PC](PC/README.md), [Android](Android/README.md), [Wallet](Wallet/README.md) and [documentation](Documentation/README.md) sections now carry the withdrawal status. [Explorer](Explorer/README.md) and [P2P](P2P/README.md) releases are separate applications; their presence does not verify or repair the node consensus rule.

No claim of 51% attack protection or network-wide agreement is established by the withdrawn implementation. A corrected design and end-to-end verification are required before another node release.
