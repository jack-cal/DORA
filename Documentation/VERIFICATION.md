# Verification and release scope

Date: 2026-10-22. Windows 0.57.33; Android 0.6.83 (versionCode 143).

## Recorded validation

- The preceding release audit recorded 1,210 passing PC cases and six environment-dependent skips across 127 modules. It combines the initial suite with targeted reruns, not duplicate test counts.
- The Android device audit recorded 13 passing UI tests, four runtime/consensus tests containing 27 Python checks, and 525 screen captures covering the 34 UI languages.
- Five independent node processes synchronized over TCP to height 9026 and agreed on two completed connection proofs. An eight-second witness delay did not block subsequent mining. A late fifth node independently checked the retained proofs.
- Mixed old/new boundary tests retained valid history through 8999 while rejecting a height-9000 block missing the mandatory producer commitment. Valid upgraded blocks did not require completed witness evidence.
- The whitepaper revision passed 18 related document, issuance, DGW and probability tests. Four sets of 34 localized HTML documents and the retained issuance sections were checked before producing this English publication.
- The 34 language editions were directly compared and edited without an external translation service. Corrections clarify conditional decompression, secret-share terminology and several grammatical ambiguities. Independent native-speaker certification is not claimed.

## What this packaging changes

The published whitepaper, technical references, README files and release notes are English. All 34 runtime UI languages remain available. Document-menu paths for other languages open the English edition. Existing users retain their saved UI language; a fresh profile defaults to English.

The Windows executable files and signed Android APK are unchanged from the audited 0.57.33/0.6.83 build. No wallet, live chain database, password, recovery material or release-signing private key is included. New source and package hashes describe this exact publication.

## Limits

Tests used isolated chains and local devices; they do not establish public height-9000 activation, worldwide candidate discovery, performance for every NAT arrangement or independent security certification. Connection proofs rank equal-work branches; greater valid cumulative work remains primary. Late evidence may change an equal-work choice. The initial beacon share group is fixed and lacks automatic resharing; loss of enough participants can prevent new proofs while mining continues.

The earlier withdrawn versions remain withdrawn. This publication specifies asynchronous signing after PoW; it does not claim that signature preparation finishes during mining. The separately withdrawn standalone wallet has not been rebuilt or reinstated.
