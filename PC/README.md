# SUMUWW Windows 0.57.46

The node validates and synchronizes the SUMUWW chain, provides a personal wallet and optional CPU mining, and retains peer recovery and asynchronous connection proofs.

Mining history separates block issuance, transaction fees, total rewards and the wallet's own received amount. Automatic fees use the connected node's current pending queue and block capacity; previous block fees are not sampled. Manual rates and a final fee review remain available. One yugeon is 0.00000001 SMW.

The API supports address and transaction inspection, signed-transaction checks and submission, UTXOs, confirmation and replacement state, reorganization information and ordered data outputs. Optional source examples run on disposable regtest data. Multisig and output-lock public activation is not scheduled.

English is the default and all 34 UI languages remain available. Preserve encrypted wallets and valid chain history. The existing height-9000 rules and height-9100 HTLC activation remain unchanged. Tests do not establish uninterrupted Internet availability or an independent security audit.

Extract the complete Windows ZIP and run SUMUWW.exe. Windows executables are not publisher-code-signed.

[Release and checksums](https://github.com/jack-cal/SUMUWW/releases/tag/pc-v0.57.46) · [Source](Source) · [Current specification](Source/NODE_FEATURES.md)
