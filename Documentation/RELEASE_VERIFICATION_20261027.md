# Windows 0.57.48 release verification — 27 October 2026

This record covers the Windows full node, wallet and miner. It does not replace the 26 October verification of other components.

## Changes

Mining submits proof-of-work blocks through the node's normal validation path. Connection evidence continues asynchronously after block acceptance and does not gate block acceptance. The source-block-9,600 upgrade and other previously published features remain included.

## Checks completed

- Eight focused mining and activated-proof cases passed.
- Ten packaged-executable smoke checks passed.
- A disposable regtest profile mined and accepted a block.
- A read-only copy of the local chain database at height 9,547 produced a valid next-block template at height 9,548. The live database was not mined or modified.
- The packaged Windows executable was checked against the built source output; the desktop executable SHA-256 is recorded in the release asset checksums.

## Limits

The generic mining error shown in the earlier desktop screenshot was not reproduced, and its underlying exception was not captured. Therefore this release cannot be represented as a verified fix for that specific screen error. No block was mined on the live mainnet, no public-network endurance test was performed, and no independent security audit is claimed.

Update all validating nodes and ordinary wallets before block 9,600. The 34 existing interface languages and saved language preferences are retained; English remains the first-launch language.
