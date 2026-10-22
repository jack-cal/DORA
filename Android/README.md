# SUMUWW Android 0.6.84

Android full node, wallet and CPU miner. Package `org.sumuww.miner`, versionCode 144; Android 8.0 or newer, arm64-v8a and x86_64. English is the default; all 34 UI languages remain available.

## Added and fixed

- Automatically prepare a fresh distributed-randomness key when the current beacon group cannot supply enough valid responses.
- Check participant health with authenticated threshold shares; retry withheld or invalid DKG contributions and unavailable prepared proposals.
- Bind each replacement to its exact predecessor and a round on the same PoW ancestry. Nodes independently validate the public setup and readiness signatures.
- Preserve completed historical proofs under their original key. Recovery does not block PoW mining or redraw old proof jobs.
- Preserve wallets, valid historical blocks, issuance, halvings, the 20% random event probability, cumulative-work priority and DGW/10 from height 9000.

- Include the same recovery implementation as Windows while retaining the original mobile icons, button layout, wallet format and saved language preference.
- Publish the APK using the existing application signing lineage so it can update the installed app without clearing its data.

## Verification

A Samsung SM-S928N running Android 16 passed 29 protocol/native-runtime cases in an isolated audit app, including ten new recovery cases and the numeric 8999/9000 boundary. The signed APK was subsequently installed over the existing app, and wallet display and chain continuity were checked. The shared implementation also passed an eight-identity process experiment with old-group loss, recovery and late verification.

## Download and update

[Android APK](https://github.com/jack-cal/SUMUWW/releases/download/android-v0.6.84/SUMUWW-Android-0.6.84.apk) · [Android source ZIP](https://github.com/jack-cal/SUMUWW/releases/download/android-v0.6.84/SUMUWW-Android-Source-0.6.84-English.zip)

Install the APK over the existing app. Do not uninstall or clear data for an ordinary update. Open the existing wallet with its own password after restarting. Check Android-SHA256SUMS.txt on the release page. The separate standalone wallet application is not part of this release.

## Compatibility and scope

Recovery requires at least three usable participants, eventual delivery and a mined commitment. Old incomplete jobs may remain incomplete if their original threshold shares are lost. Validating nodes must upgrade before new recovery records are used. The protocol remains experimental; local checks are not an independent cryptographic audit or a multi-day public-network trial.

[Source](Source) · [Recovery protocol](../Documentation/BEACON_RECOVERY.md) · [Verification](../Documentation/BEACON_RECOVERY_VERIFICATION.md)
