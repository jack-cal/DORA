# Wallet recovery and distribution repair — 2026-10-24

This is a local, unpublished revision. Windows ordinary wallet **1.0.2** and
Android Wallet Current **1.1.2**, versionCode **13**, include the current connection
recovery and synchronization changes from core 0.57.38 / Android 0.6.88.
Windows full-node 0.57.38, Explorer 0.4.6 and P2P Full/Light 0.3.0 packages marked **docs-r2** contain
documentation/dependency-record corrections; their executable bytes are unchanged.
The Android full-node APK remains 0.6.88. Earlier publication records identify
their original assets, not these new local archives. Nothing was uploaded to GitHub.

## Code changes

The Windows wallet is rebuilt against the current shared desktop core. Android
receives the corresponding Android chain, link_runtime, peer, peer_discovery,
wire and core-version modules; platform adapters and app identity are retained.
Verified peers survive temporary failures; failure accounting is not duplicated
or converted into success after a response timeout. Missing inbound listener
hints are independently verified before sharing. Public outgoing handshakes and
responses have bounded 120-second waits while partial frames keep short deadlines.
Validated ancestry is reused only for a matching snapshot, height and hash.
Background proof-history work yields between jobs.

Wallet formats, addresses, balances, valid history and consensus are unchanged.
No production wallet was opened, restored, spent or mined during this work.
All 34 UI language catalogs and saved language preferences are retained. No new
UI strings were required. The Korean companion guide was written directly;
no external automatic translation service was used.

## Checks performed on the corrected build

| Check | Result |
|---|---|
| Windows current-core connection/history regressions | 22 passed |
| Android-wallet current-core connection/history regressions on host | 22 passed |
| Connection-proof validation and propagation regressions | 20 passed |
| Windows wallet UI/locking/payment-review regressions | 9 passed |
| Android-wallet disposable wallet/backup/payment-flow host checks | 10 passed |
| Android JVM language/layout checks | 4 passed |
| Rebuilt Windows executable self-check | 6 checks passed; version 1.0.2 |
| Compiled core vs corrected source | Six modules match in each final wallet |
| Android release build and signature verification | Passed; v2/v3 signatures |
| Windows dependency resolution with complete hash lock | 16 packages resolved from verified wheels |

The frozen Windows self-check covers encrypted-wallet creation, backup
authentication, locking, same-address restoration, unavailable mining commands
and 34 language catalogs. All wallet and network fixtures use disposable data
and owned local test connections. The Android APK retains application ID
`org.sumuww.wallet.current`, minSdk 26, targetSdk 35 and arm64-v8a/x86_64 support.
Certificate SHA-256:
`e6b41f98b4c965a76072277b8ea258553901bd7f9fd9b1c3120b567e6212e80a`.

## Dependency and packaging corrections

Five Windows declarations now match the bundled versions: cffi 2.1.1,
cytoolz 1.2.0, eth-typing 6.0.0, eth-utils 6.0.0 and pycparser 3.12.
The lock includes the complete 16-package runtime closure, including Pydantic
dependencies. Wheel SHA-256 values were checked against official PyPI version
metadata, and licenses/provenance were updated. Both Windows build entry points
reject a version mismatch between requirements, the hash lock and the environment.
Android has separate ABI-specific pins; matching Windows versions is not required.

Current copied guides are updated at their actual location. Broken relative
document/license links are repaired. Historical verification and changelog records
are labeled by scope. Current and previously published versions are not conflated.
Each local component checksum file uses paths relative to its own directory.
The root SHA256SUMS.txt covers every distribution file except itself and
FILE_HASHES.json. FILE_HASHES.json additionally covers SHA256SUMS.txt and excludes
only itself, so nested checksum files are included.

SOURCE_FILES.json inside each new source archive records the exact snapshot.
SOURCE_COMMIT.txt identifies the base commit plus local changes; it does not
misrepresent the archive as the unchanged published commit. Final archive,
link, runtime-preservation and checksum results are recorded separately in
DISTRIBUTION_VERIFICATION.json in the desktop Technical documentation.

## Limits and historical test findings

Two older Android full-node test modules were evaluated as possible regression
fixtures. Five assertions/errors in six test cases failed identically against
the unchanged current full-node source and the updated wallet. They assume an
older per-stage local-handshake deadline and retention/protocol cycling of
unverified failed contacts. They are not the current public-peer policy and were
not copied into the wallet release. The original full-node fixtures were not
altered. The current 22-case recovery suite tests the present policies directly.
This is not a claim that every historical test in the repository passes.

No physical Android device, Internet endurance, new public-chain mining or
public-money transfer test was run for this repair. Previous physical-device
results are historical evidence only. External peer availability and uninterrupted
connectivity remain unproven. Windows executable publisher signing is unchanged.
