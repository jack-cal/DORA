# SUMUWW PC 0.57.33

Windows AMD64 node, wallet and miner. English is the default for a fresh profile.

## Updates and fixes

- Document the asynchronous connection proof for exact parent/child blocks A/B: three Ed25519 signatures, six halves, two paired bundles and producer receipts.
- Use a 20% random connection-event probability. Mining, block acceptance and propagation do not wait for completed signatures.
- Keep cumulative valid work primary; count nonconflicting connections only for equal-work branches and neutralize conflicting positions.
- Preserve valid history through height 8999, including a valid prefix delivered with an invalid later continuation. Require the producer commitment on every block from 9000.
- Retain the 24-block DGW v3 calculation and apply it at 9000, 9010, 9020 and subsequent ten-block boundaries. Preserve issuance, halvings, maturity, wallets and existing valid coins.
- Rewrite the whitepaper around connection evidence, remove repetitive material, correct obsolete 10% metadata and include the missing height-9100 HTLC reference.
- Publish English documentation and release notes, while retaining all 34 application UI languages.

- Correct the difficulty display to show the ten-block adjustment interval after height 9000.
- Include the complete portable runtime, icons, document menus, node manager and required dependency licenses.
- Align the network and discovery regression fixtures with current asynchronous proof behavior; this is not a claim of new production networking performance.

## Installation

Extract the entire Windows ZIP into a new folder and run SUMUWW.exe. Keep _internal, assets, docs, programs and the other bundled files together. Close the old application before using the same data directory. Keep the existing encrypted wallet and node database; do not reset either. Python does not need to be installed separately for the executable package.

The source ZIP includes the Python application, tests, build instructions and vendored dependency notices. The Windows executables are unsigned by a publisher certificate.

## Verification and limitations

See VERIFICATION.md for the recorded checks and limits. This is an experimental protocol release, not independent security certification. The prior withdrawn releases remain withdrawn; this version deliberately requests witness signatures after PoW.
