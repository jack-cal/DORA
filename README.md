# SUMUWW (SMW)

Independent SHA-256d proof-of-work blockchain with node, wallet, mining and local inspection applications.

## Downloads and version history

Choose a component. Every section includes its latest application, matching source, checksums, installation instructions and previous releases.

| Component | Version | Open section |
|---|---|---|
| PC | 0.57.28 | [PC: downloads and history](PC/README.md) |
| Android | 0.6.78 | [Android: downloads and history](Android/README.md) |
| Wallet | 1.0.9 | [Wallet: downloads and history](Wallet/README.md) |
| Explorer | 0.4.4 | [Explorer: downloads and history](Explorer/README.md) |
| P2P | 0.1.6 | [P2P: downloads and history](P2P/README.md) |
| Documentation | Current unified edition | [Guide, whitepaper and protocol](Documentation/README.md) |

PC and Android are published separately. Component version numbers are independent. Historical releases and download records are preserved.

## Network and applications

- SHA-256d PoW, independent block/transaction validation and UTXO accounting.
- Target block interval: 600 seconds. DGW v3 difficulty from height 8064.
- Random BLS block-signature linkage from height 9000, selected with 10% probability per parent/height context.
- Exact-template SHA256/preimage/CLTV conditional spending from height 9100. Existing mature coins remain usable.
- English first-launch default and 34 bundled languages with a saved language selector.
- Standalone wallet, local explorer and native P2P application are separate downloads. P2P public-money swaps remain disabled; its exchange execution is regtest-only.

Nominal maximum issuance: **17,999,999.97690000 SMW**; excluding the unspendable genesis reward: **17,999,949.97690000 SMW**. Transaction fees transfer existing value to the block miner. Reward maturity requires a creation-to-spending height difference of at least 100.

Read the [unified guide](Documentation/README.md) for consensus rules, installation, privacy, compatibility, verification scope and source builds. Named source ZIPs contain implementation; automatic GitHub source archives contain this documentation repository.

## Archive

[Earlier documentation and whitepaper images](Archive/README.md). Current documentation is in [Documentation](Documentation/README.md); historical application downloads are listed within each component.
