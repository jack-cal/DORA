# SUMUWW current releases — 26 October 2026

| Program | Version |
|---|---|
| Windows full node | 0.57.47 |
| Android full node | 0.6.96 |
| Windows ordinary wallet | 1.0.8 |
| Android ordinary wallet | 1.1.7 |
| Explorer | 0.4.11 |
| P2P Full / Light | 0.3.5 |

[Downloads and matching sources](../README.md) · [Installation](COMPONENT_SUITE.md) · [Verification](RELEASE_VERIFICATION_20261026.md)

Update validating full nodes and ordinary wallets before block **9,600**. The source-block 9,600 rule certifies the active candidate set used to select three connection-proof witnesses. After activation, pending jobs can renew their activity round while retaining their original block pair and event beacon. Earlier valid history and proofs remain valid. Missing proofs do not prevent ordinary proof-of-work block acceptance. Old and upgraded software can select different equal-work branches.

English is the first-launch language for every program. Saved language preferences and all 34 selectable languages are preserved. The detailed technical whitepaper 2.3 is in English; all 34 languages include directly authored summaries and correction notices, not full technical translations.

Mining history distinguishes new issuance, transaction fees, total rewards and the amount received by the wallet. Automatic fee suggestions use the connected node's current pending queue, not past-block fee samples. One yugeon is 0.00000001 SMW; vB is a data-size unit.

Both Android packages are installation files; physical-phone installation or execution of these versions is not claimed. The verification used isolated test chains and temporary profiles. It does not establish public-network completion of previously pending proof jobs or uninterrupted availability.

Earlier release posts, assets and dated verification reports retain their original scope. The current application and document releases are separate from that history.
