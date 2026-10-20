# SUMUWW Android

[All components](../README.md) · [Unified guide](../Documentation/README.md) · [Version history](#version-history)

Android full node, wallet and CPU miner.

## Latest — 0.6.79

| File | Download |
|---|---|
| RELEASE_NOTES.txt | [Download](https://github.com/jack-cal/SUMUWW/releases/download/android-v0.6.79/RELEASE_NOTES.txt) |
| SHA256SUMS.txt | [Download](https://github.com/jack-cal/SUMUWW/releases/download/android-v0.6.79/SHA256SUMS.txt) |
| SUMUWW-Android-0.6.79.apk | [Download](https://github.com/jack-cal/SUMUWW/releases/download/android-v0.6.79/SUMUWW-Android-0.6.79.apk) |
| SUMUWW-Android-Source-0.6.79.zip | [Download](https://github.com/jack-cal/SUMUWW/releases/download/android-v0.6.79/SUMUWW-Android-Source-0.6.79.zip) |

Full node, wallet and mining application. Exact-template P2WSH SHA256/preimage/CLTV spending activates at block **9100**; the separate random-10% BLS block-signature rule remains at **9000**. Existing mature common-history coins remain usable.

Install the signed APK over the existing application. Do not uninstall or clear data. Preserve the encrypted wallet and node data.

At selected signature blocks, a quiet discovery interval no longer stops the current mined candidate. It remains pending until a third currently responding, distinct-IP signer appears. The three-signature requirement, random 10% selection from height 9000, PoW and height-9100 conditional-spending rules are unchanged. Final signatures are still collected after PoW.

This release contains only the Android application and its matching implementation source. PC 0.57.30 is published separately.


## Version history

All published historical assets remain available. Older combined PC/Android releases are listed under both matching components; current platform releases are separate.

| Published (UTC) | Release | Application | Source |
|---|---|---|---|
| 2026-10-20 | [SUMUWW Android 0.6.79](https://github.com/jack-cal/SUMUWW/releases/tag/android-v0.6.79) | [Android APK](https://github.com/jack-cal/SUMUWW/releases/download/android-v0.6.79/SUMUWW-Android-0.6.79.apk) | [Source ZIP](https://github.com/jack-cal/SUMUWW/releases/download/android-v0.6.79/SUMUWW-Android-Source-0.6.79.zip) |
| 2026-10-20 | [SUMUWW Android 0.6.78](https://github.com/jack-cal/SUMUWW/releases/tag/android-v0.6.78) | [Android APK](https://github.com/jack-cal/SUMUWW/releases/download/android-v0.6.78/SUMUWW-Android-0.6.78-HTLC9100.apk) | [Source ZIP](https://github.com/jack-cal/SUMUWW/releases/download/android-v0.6.78/SUMUWW-Android-Source-0.6.78.zip) |
| 2026-10-20 | [SUMUWW Windows 0.57.28 / Android 0.6.78](https://github.com/jack-cal/SUMUWW/releases/tag/smw-0.57.28-0.6.78) | [Android APK](https://github.com/jack-cal/SUMUWW/releases/download/smw-0.57.28-0.6.78/SUMUWW-Android-0.6.78-HTLC9100.apk) | [Source ZIP](https://github.com/jack-cal/SUMUWW/releases/download/smw-0.57.28-0.6.78/SUMUWW-source-0.57.28-0.6.78-HTLC9100.zip) |
| 2026-10-19 | [SUMUWW Windows 0.57.27 / Android 0.6.77](https://github.com/jack-cal/SUMUWW/releases/tag/smw-0.57.27-0.6.77) | [Android APK](https://github.com/jack-cal/SUMUWW/releases/download/smw-0.57.27-0.6.77/SUMUWW-Android-0.6.77.apk) | [Source ZIP](https://github.com/jack-cal/SUMUWW/releases/download/smw-0.57.27-0.6.77/SUMUWW-source-0.57.27-0.6.77.zip) |
| 2026-10-19 | [SUMUWW Windows 0.57.26 / Android 0.6.76](https://github.com/jack-cal/SUMUWW/releases/tag/smw-0.57.26-0.6.76) | [Android APK](https://github.com/jack-cal/SUMUWW/releases/download/smw-0.57.26-0.6.76/SUMUWW-Android-0.6.76.apk) | [Source ZIP](https://github.com/jack-cal/SUMUWW/releases/download/smw-0.57.26-0.6.76/SUMUWW-source-0.57.26-0.6.76.zip) |
| 2026-10-16 | [SUMUWW Android 0.6.53](https://github.com/jack-cal/SUMUWW/releases/tag/android-v0.6.53) | [Android APK](https://github.com/jack-cal/SUMUWW/releases/download/android-v0.6.53/SUMUWW_Android_v0_6_53.apk) | [Source ZIP](https://github.com/jack-cal/SUMUWW/releases/download/android-v0.6.53/SUMUWW_Android_Source_v0_6_53.zip) · [SUMUWW_Android_Source_v0_6_53.zip.sha256](https://github.com/jack-cal/SUMUWW/releases/download/android-v0.6.53/SUMUWW_Android_Source_v0_6_53.zip.sha256) |
| 2026-10-15 | [SUMUWW Android 0.6.52](https://github.com/jack-cal/SUMUWW/releases/tag/android-v0.6.52) | [Android APK](https://github.com/jack-cal/SUMUWW/releases/download/android-v0.6.52/SUMUWW_Android_v0_6_52.apk) | [Source ZIP](https://github.com/jack-cal/SUMUWW/releases/download/android-v0.6.52/SUMUWW_Android_Source_v0_6_52.zip) · [SUMUWW_Android_Source_v0_6_52.zip.sha256](https://github.com/jack-cal/SUMUWW/releases/download/android-v0.6.52/SUMUWW_Android_Source_v0_6_52.zip.sha256) |
| 2026-10-14 | [SUMUWW Android 0.6.45](https://github.com/jack-cal/SUMUWW/releases/tag/android-v0.6.45) | [Android APK](https://github.com/jack-cal/SUMUWW/releases/download/android-v0.6.45/SUMUWW_Android_v0_6_45.apk) | [Source ZIP](https://github.com/jack-cal/SUMUWW/releases/download/android-v0.6.45/SUMUWW_Android_Source_v0_6_45.zip) · [SUMUWW_Android_Source_v0_6_45.zip.sha256](https://github.com/jack-cal/SUMUWW/releases/download/android-v0.6.45/SUMUWW_Android_Source_v0_6_45.zip.sha256) |
| 2026-10-12 | [SUMUWW Android 0.6.41](https://github.com/jack-cal/SUMUWW/releases/tag/android-v0.6.41) | [Android APK](https://github.com/jack-cal/SUMUWW/releases/download/android-v0.6.41/SUMUWW_Android_v0_6_41.apk) | — |
