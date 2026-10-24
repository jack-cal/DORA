# Current releases and documentation — 24 October 2026

| Component | Current download | Scope |
|---|---|---|
| PC full node | [0.57.40](https://github.com/jack-cal/SUMUWW/releases/tag/pc-v0.57.40) | Proof availability repair and public history |
| Android full node | [0.6.89](https://github.com/jack-cal/SUMUWW/releases/tag/android-v0.6.89) | Proof availability repair |
| PC ordinary wallet | [1.0.2](https://github.com/jack-cal/SUMUWW/releases/tag/wallet-pc-v1.0.2) | Connection recovery and synchronization |
| Android ordinary wallet | [1.1.2](https://github.com/jack-cal/SUMUWW/releases/tag/wallet-android-v1.1.2) | Same recovery repair; Current signing identity retained |
| Explorer | [0.4.6 docs-r3](https://github.com/jack-cal/SUMUWW/releases/tag/explorer-v0.4.6-docs-r3) | Current guide and proof scope; unchanged executable |
| P2P Full | [0.3.0 docs-r2](https://github.com/jack-cal/SUMUWW/releases/tag/p2p-full-v0.3.0-docs-r2) | Corrected setup/download guidance; unchanged executable |
| P2P Light | [0.3.0 docs-r2](https://github.com/jack-cal/SUMUWW/releases/tag/p2p-light-v0.3.0-docs-r2) | Corrected setup/download guidance; unchanged executable |
| English whitepaper | [2.2](https://github.com/jack-cal/SUMUWW/releases/tag/whitepaper-v2.2-en) | Current witness policy, counters and verification scope |
| Documentation | [20261024-r1](https://github.com/jack-cal/SUMUWW/releases/tag/docs-20261024-r1) | Common documents, evidence and source-document corrections |

Each link identifies a separate release. Earlier release posts, assets and checksums
remain unchanged. Publication, preparation and installation are separate states:
publishing these packages does not replace the operating desktop full node.

## Erratum for older embedded documentation

Some whitepaper/recovery copies bundled in the original full-node archives
describe sampling every discovered identity without a fresh response check.
PC 0.57.40 / Android 0.6.89 actually probe the complete discovered inventory and
select three responding identities using the verified beacon. Already selected
jobs retain their original witnesses. Whitepaper 2.2 and current source documents
correct that prose. The original full-node archives and matching hashes remain
immutable; this document update does not change their executable behavior.

Wallet source ZIPs preserve the verified build snapshots, including the core used
for those wallet builds. They are not regenerated using newer producer-job code.
SOURCE_FILES.json identifies their exact inputs, and SOURCE_COMMIT.txt explains
the snapshot provenance. Ordinary wallets respond to current signed probes but
do not run the miner's producer jobs. Nested historic core guides describe their
build-era context; use the current whitepaper for 0.57.40 / 0.6.89 producer policy.

[Component guide](COMPONENT_SUITE.md) ·
[Connection repair verification](CONNECTION_PROOF_REPAIR_VERIFICATION.md) ·
[Whitepaper](Whitepaper/WHITEPAPER.md)

## Historical evidence

Verification reports and publication JSON retain the versions and dates they
actually measured. The old PUBLICATION_CHECKS.json covers 0.57.34 / 0.6.84 and
whitepaper 2.1. LOCAL_REPAIR_VERIFICATION.md records the earlier wallet/dependency
repair and its then-current publication status; it is not the current release
manifest. Historical device or network tests are not tests of every later build.
