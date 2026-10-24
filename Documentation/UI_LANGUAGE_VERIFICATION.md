> Historical test record for the versions and dates below. Current release and local preparation status: [CURRENT_STATUS.md](CURRENT_STATUS.md). These results are not new measurements of later builds.

# UI, language and packaged-application verification

Date: 2026-10-22. Release versions: Windows wallet 1.0.1, Android Wallet Current 1.1.1 (versionCode 12), P2P 0.1.9 and Explorer 0.4.6.

The full node packages remain Windows 0.57.34 / Android 0.6.84. This release contains UI, localization, regression-test and documentation changes. Core consensus, issuance, halving and wallet file formats are unchanged. Earlier verification reports are historical records; this report supersedes the component suite's earlier statement that no physical Android device was available.

## Corrections

- Windows wallet: clear the recovery-word dialog when locked, minimized or closed; retain the selected lock timeout after restart; distinguish catching up from synchronized; localize common errors; disable unavailable wallet actions; support vertical Mongolian captions and scrolling in smaller windows.
- Android wallet: fit translated Lock, Send, Receive and navigation captions instead of cropping them at fixed heights. Preserve Wallet Current's application ID and signing certificate for in-place upgrades from 1.1.0.
- Wallet catalogs: correct connected-node/block terminology in 26 languages, with identical 119-key catalogs on PC and Android.
- P2P: wrap action rows and descriptions, separate header status, balance summary columns, and scroll wide forms. Correct one German test-action caption.
- Explorer: correct 164 entries across 19 languages and synchronize the browser language bundle with the catalogs.

Translations were written directly without external translation services. English is the publication and fresh-profile default. Saved language choices remain available. Protocol identifiers, addresses, hashes and numeric values are not translated.

## Recorded checks

| Area | Result and scope |
|---|---|
| Windows full-node UI baseline | 32 tests passed; disposable create/restore, payment controls, history, network/RPC and language coverage |
| Windows wallet | Nine native regression tests passed, including automatic-lock recovery-dialog closure, persisted timeout, synchronization labeling, localized password errors and payment-review cancellation in all 34 languages |
| Windows wallet layout | 204 combinations: 34 languages, three pages, two window sizes; no inaccessible controls in the measured cases |
| Frozen Windows wallet | Disposable creation, encrypted backup, lock, same-address restore, 34 catalogs and rejection of mining commands passed |
| P2P | 81 regression tests and 13 focused native UI/language tests passed |
| P2P layout | 408 combinations: 34 languages, six tabs, two sizes; wide fields remained reachable through the horizontal scrollbar |
| Frozen P2P | Two separate local TCP processes with SMW/BTC regtest chains exercised RPC reads, claims and restart/refund recovery |
| Explorer | 150 Python test executions, including inherited repeated cases, and 43 JavaScript UI tests passed |
| Packaged explorer browser | All 34 languages, six navigation sections and block-height search checked; language switching preserved the block hash and no console errors were observed |
| Android JVM | Four tests passed; the new caption check covered 204 combinations (34 languages, three pages, two widths), with zero remaining measured clipping cases |
| Android physical device | Samsung SM-S928N: seven baseline instrumentation scenarios passed; six corrected-build scenarios passed, followed by the corrected new navigation harness passing separately. The final catalog navigation rerun passed. The app reached height 8949 with three peers |
| Catalog integrity | 34 languages per app, wallet 119 keys, P2P 221 and explorer 182; no missing/empty keys, replacement characters or placeholder mismatches; PC/Android wallet catalogs identical |

The corrected Android application logic was exercised before the final metadata bump from 1.1.0 to 1.1.1. The release APK is rebuilt and checked for signature, alignment, application ID and version. This distinction avoids presenting an earlier physical-device run as a test of a byte-identical release APK.

Physical-device protocol instrumentation covers current connection proofs, beacon recovery, transport, legacy transport, 20% events, DGW/10 and mixed-batch activation-prefix handling. Temporary wallets and isolated regtest funds were used for payment tests. The user's existing full-node/miner and personal wallet were not migrated, cleared or spent from. A live synchronization observation is not evidence of public-network activation at height 9000.

The desktop lock fix was reproduced before correction. Android's initial caption measurement found 129 clipping observations across 12 languages; the corrected measurement found zero. A new device test initially clicked before a dialog had finished closing; adding a wait fixed the test, and its rerun passed. No unresolved failure from those checks is counted as a pass.

## Installation and limits

Keep encrypted backups. Extract complete Windows ZIPs. Wallet Current 1.1.1 upgrades Wallet Current 1.1.0 with the same application ID and signer. It cannot replace the old differently signed `org.sumuww.wallet`; preserve the old app and restore its encrypted backup or recovery words in Current. Ordinary wallets validate and store the chain locally; the explorer only reads a selected node database.

These are local checks on the recorded sizes, languages and device. They do not prove correctness on every device, translation perfection, Internet-scale robustness, an independent security audit or irreversible finality. Public-money P2P swaps remain disabled. The experimental connection proof does not override greater valid cumulative work.

## Required upgrade at height 9,000

**From block 9,000 inclusive, blocks created under the old pre-upgrade rules are rejected by upgraded nodes. Update miners and validating nodes.** Valid legacy history through **8,999 remains usable**, including the valid prefix of a mixed synchronization batch. Wallet keys, valid coins, issuance and halvings are preserved. Validation follows block rules, not an advertised version string.

This patch does not change consensus. The existing 20% asynchronous post-PoW connection events, three witnesses, DGW recalculation every ten blocks using 24 prior blocks, and HTLC activation at 9100 remain unchanged. Mining does not wait for completed witness signatures. Valid cumulative work remains primary.

## Sources and downloads

The repository includes the production changes and regression tests. Each patched application has a separate binary release, matching source archive, English notes and SHA-256 checksums. Private signing keys, passwords, user wallets, node databases and disposable test state are excluded.

[Component suite and migration](COMPONENT_SUITE.md) · [All downloads](https://github.com/jack-cal/SUMUWW/releases)
