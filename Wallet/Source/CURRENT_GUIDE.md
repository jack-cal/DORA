SUMUWW Wallet Current 1.1.6 — Android

Ordinary wallet with send, receive, transaction history, encrypted backups,
recovery words, automatic lock, and 34 offline interface languages. English is
the first-launch default. Existing artwork and wallet UI are retained.

This is a separate application, org.sumuww.wallet.current. It does not overwrite
or uninstall the withdrawn org.sumuww.wallet application. The old application's
signing key was not found in this workspace, so an in-place update cannot be
claimed. Keep the old application and its data. Import an encrypted backup or
restore the recovery words in the new app to retain the same address and keys.
Never share a password or recovery phrase. The original wallet is not modified.

The wallet uses SUMUWW PC 0.57.46 / Android 0.6.95 validation code validation code. Valid legacy
blocks through 8999 are retained; old-rule blocks at 9000 and later are rejected.
Post-PoW connection events use a 20% probability. A block producer collects three
witness signatures after mining, splits each into two parts and binds evidence
to the exact parent/child pair. Mining and block acceptance never wait for this
proof. Valid cumulative work stays primary. Completed evidence can resolve equal
work; it does not guarantee finality. Threshold beacon recovery is included.
DGW uses a 24-block window and adjusts at 9000, 9010, 9020, and so on. Existing
issuance and halving rules remain unchanged. HTLC spending activates at 9100.

This is a validating wallet without mining controls, not an SPV/light client.
It synchronizes and stores the chain locally. A peer connection is required for
new blocks and transactions. Public-money swaps are not part of this wallet.

Build with JDK 17, Gradle 8.10.2, Python 3.13, Android SDK 35, NDK 27.2.12479018
and CMake 3.22.1. Set local.properties and DORA_BUILD_PYTHON locally, then run
assembleRelease and testDebugUnitTest. Private signing material is never included.
This update retains the SUMUWW Wallet Current 1.1.0 signing
identity, different from the original standalone-wallet certificate. Future
Current updates must retain this key. Private signing material stays outside
source and releases. Set SUMUWW_WALLET_SIGNING_DIR and ANDROID_SDK_ROOT, then
use tools/sign_release.py to sign a prepared release APK.

Host tests: tools/check_wallet_host.py, plus the current pc_tests protocol suite.
Android instrumentation: CurrentLinksTest uses disposable files in the cache.
Older V4 tests are historical fixtures and are not the current activation design.
Do not treat a successful build or host test as physical Android verification.

Version 1.1.2 (versionCode 13) updates Wallet Current 1.1.0 in place with the
same application ID and certificate. See the repository UI_LANGUAGE_VERIFICATION
report for historical physical-device and multilingual caption checks.
Those earlier device results are not a physical-device test of version 1.1.2.
See RELEASE_NOTES.txt for the current build and verification scope.

## 1.1.6

1 SMW = 100,000,000 yugeon. Automatic fees offer slow, normal and fast presets based on local observations; they do not guarantee confirmation times. You can enter a rate in yugeon/vB manually. Review the final fee and total in SMW before sending. A rejected transaction does not debit your balance.

[Current features in 34 languages](docs/features/index.html).
