# SUMUWW (SMW)

SUMUWW is an independent Proof-of-Work cryptocurrency with Windows and Android node, non-custodial wallet and mining applications. The private keys remain with the wallet user.

## Downloads and source code

| Component | Current release | Source archive |
| --- | --- | --- |
| Windows node / wallet / miner | [0.57.21](https://github.com/jack-cal/SUMUWW/releases/tag/pc-v0.57.21) | [SUMUWW_Source_v0_57_21.zip](https://github.com/jack-cal/SUMUWW/releases/download/pc-v0.57.21/SUMUWW_Source_v0_57_21.zip) |
| Android node / wallet / miner | [0.6.53](https://github.com/jack-cal/SUMUWW/releases/tag/android-v0.6.53) | [SUMUWW_Android_Source_v0_6_53.zip](https://github.com/jack-cal/SUMUWW/releases/download/android-v0.6.53/SUMUWW_Android_Source_v0_6_53.zip) |
| Local block explorer | [0.4.0](https://github.com/jack-cal/SUMUWW/releases/tag/explorer-v0.4.0) | [SUMUWW_Explorer_Source_v0_4_0.zip](https://github.com/jack-cal/SUMUWW/releases/download/explorer-v0.4.0/SUMUWW_Explorer_Source_v0_4_0.zip) |

**Source distribution:** the implementation, tests, build instructions, whitepaper and protocol documentation are distributed in the named source ZIP assets attached to Releases. This repository branch currently contains this index, not the implementation tree. GitHub's automatically generated “Source code (zip/tar.gz)” downloads contain the repository tree and are **not** the implementation archives above. Each release provides SHA-256 checksum files. Historical releases are retained.

## Consensus parameters

These are implementation parameters, not claims of an independent audit. See `SUMUWW_PROTOCOL_SPEC.md`, `WHITEPAPER.md`, `dora/primitives.py`, `dora/profiles.py` and `dora/difficulty.py` in the Windows source archive.

| Parameter | Rule |
| --- | --- |
| Proof of Work | SHA-256d (double SHA-256) |
| Target average block interval | 600 seconds; actual intervals vary |
| Difficulty before height 8,064 | Adjustment every 2,016 blocks |
| Difficulty from height 8,064 | DGW v3, recalculated for each block from the preceding 24 blocks on the same parent branch |
| Chain selection | Greatest cumulative work among valid branches |
| Nominal maximum issuance | 17,999,999.97690000 SMW |
| Maximum excluding the unspendable genesis reward | 17,999,949.97690000 SMW |
| Block subsidy | 50 SMW at heights 0–149,999; 25 SMW from 150,000, then halved every 210,000 blocks using integer smallest units |
| Smallest unit | 0.00000001 SMW |
| Coinbase maturity | Spending height minus creation height must be at least 100 |
| Address format | Bech32, `sumuww` prefix, native P2WPKH |
| Genesis hash | `00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97` |

GPU/ASIC selection becomes available in the official applications at verified height 12,000. This application setting is not proof that the network can identify or prohibit other miners' hardware. DGW adjusts difficulty; it does not prevent majority-hash attacks.

## Explorer

Explorer 0.4.0 is a **local, read-only application**. It reads a synchronized SUMUWW node database and opens `http://127.0.0.1:8770` on the user's computer. That address is local to each computer; it is not a publicly hosted explorer website. The explorer does not synchronize a node, mine, access wallet keys or send transactions. Its data and confirmations reflect the selected node's active chain.

## Current connection update and validation limits

Windows 0.57.21 and Android 0.6.53 revise peer admission: up to 32 steady sessions per node, eight outgoing opportunities reserved, and one shared, bounded temporary verification connection before an incoming path is replaced. These are connection budgets, not a global node count, miner count or fixed display value.

The release notes describe the completed regression, packaged application and Android emulator tests, automatic discovery/reconnection checks and local chain replay through height 8,143. These are project-run checks, not an independent security audit. Installation and 5G reconnection of this latest APK on a real phone remain unverified.

## Installation and wallet backup

- Windows: extract the entire application ZIP and run `SUMUWW.exe`; keep the included files and `_internal` directory together.
- Android: install the signed APK over the existing app. Do not uninstall or clear app data to update. Keep a separate wallet backup.
- Explorer: extract the entire Windows ZIP and run `start-explorer.cmd` or `SUMUWW-Explorer.exe`; follow its README to select a synchronized node database.
- Keep private keys, wallet passwords and recovery words private. Running an application alone does not guarantee mining rewards.
