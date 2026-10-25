# Release verification — 26 October 2026

Applies to Windows node 0.57.47, Android node 0.6.96, Windows wallet 1.0.8, Android wallet 1.1.7, P2P Full/Light 0.3.5, Explorer 0.4.11 and whitepaper 2.3.

## Functional checks

- Node: 143 test modules passed after correcting obsolete fee, history and replay fixtures. A disposable 32-node ring completed 32 blocks and eight restarts in 325.659 seconds. Source-block-9,600 selection certificates, renewed rounds, persisted retry state and transport bounds were covered.
- P2P: 14 modules covered Full/Light interoperability, submission rejection, funding references, manual/current-queue fees, fee-increase children, cancellation and chain-local refund rules. The extended Light suite passed 46 tests in 546.786 seconds.
- Windows ordinary wallet: 11 tests and native interface checks passed. The core version footer now reads the bundled runtime version.
- Android full node: host bridge tests and 1,088 rendered screen cases (34 languages, 16 screens, two widths), 11,560 widget clicks and 10,880 dispatched actions completed without reported clipping. These are automated host checks, not physical-device execution.
- Android ordinary wallet: four Robolectric test cases cover all 34 languages, controls, saved preferences and English startup with Korean system settings. Both APKs retain their respective application identities and signing certificates.
- Explorer: seven server test modules, 47 JavaScript checks, 204 language/navigation combinations and 102 layouts passed. PDF exports were checked in all 34 languages without losing displayed amounts. The database remains read-only.
- Documents: the prepublication audit checked 1,725 HTML files and 242 Markdown files with no broken local links; 198 non-Korean locale catalogs contained no Hangul/Khmer/replacement-character contamination. Publication metadata and links are checked again when packaging.

## Language and publication

English is the default for fresh profiles in all seven programs, independent of operating-system language. Explicit saved choices remain available. The detailed whitepaper is English; 34 directly authored localized summaries and correction notices identify their scope. No external automatic translation service was used.

The release assets contain matching sources and SHA-256 checksums. Publication-only document updates do not change the audited runtime code. The full-node Android APK is rebuilt if its bundled documentation changes; its signer and compiled core are compared to the audited APK. Other audited executables are retained byte for byte.

## Limits

Tests use disposable chains, synthetic balances and temporary profiles. No real-fund trade or physical-phone installation of these versions is claimed. The tests do not establish that the nine previously pending public-network proof jobs have completed, that all users have upgraded, or that connectivity is uninterrupted. Proof completion still needs the required upgraded participants. No independent security audit is claimed. General multisig/output-lock public activation remains unscheduled.
