# SUMUWW Android 0.6.83

Android node, wallet and CPU miner. Package org.sumuww.miner, versionCode 143; Android 8.0 or newer, arm64-v8a and x86_64. English is the default for a fresh profile.

## Updates and fixes

- Document the asynchronous connection proof for exact parent/child blocks A/B: three Ed25519 signatures, six halves, two paired bundles and producer receipts.
- Use a 20% random connection-event probability. Mining, block acceptance and propagation do not wait for completed signatures.
- Keep cumulative valid work primary; count nonconflicting connections only for equal-work branches and neutralize conflicting positions.
- Preserve valid history through height 8999, including a valid prefix delivered with an invalid later continuation. Require the producer commitment on every block from 9000.
- Retain the 24-block DGW v3 calculation and apply it at 9000, 9010, 9020 and subsequent ten-block boundaries. Preserve issuance, halvings, maturity, wallets and existing valid coins.
- Rewrite the whitepaper around connection evidence, remove repetitive material, correct obsolete 10% metadata and include the missing height-9100 HTLC reference.
- Publish English documentation and release notes, while retaining all 34 application UI languages.

- Carry the validated mobile runtime and wallet-opening fixes from the preceding update into the signed 0.6.83 package.
- Retain the original icon assets, layouts, language choices, wallet format, consent controls and mining protections.
- Verify UI actions and consensus boundary behavior in the isolated Android audit package; the signed production APK keeps the original signing lineage.

## Installation

Install the signed APK over the existing org.sumuww.miner app. Do not uninstall the app or clear its data for an ordinary update. Keep an encrypted wallet backup and open the existing wallet with its own password. This release does not update or reinstate the separate standalone wallet application.

The source ZIP includes the Kotlin UI, Python node code, native dependencies, tests and build configuration. Private release-signing keys and local SDK configuration are excluded. A custom build cannot replace the official app unless signed with a compatible key.

## Verification and limitations

See [verification](../Documentation/VERIFICATION.md) for the recorded checks and limits. This is an experimental protocol release, not independent security certification. The prior withdrawn releases remain withdrawn; this version deliberately requests witness signatures after PoW.

[Download Android 0.6.83](https://github.com/jack-cal/SUMUWW/releases/tag/android-v0.6.83) · [Source](Source)
