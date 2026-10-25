Core version label now reads the bundled runtime version. Release 1.0.8: https://github.com/jack-cal/SUMUWW/releases/tag/wallet-pc-v1.0.8.

SUMUWW 1.0.8 — update before block 9,600. See UPGRADE_9600.md and the local 34-language upgrade9600 guide.

# SUMUWW Wallet for Windows 1.0.8

An ordinary wallet with receive, send, activity, encrypted backup, recovery,
automatic lock and 34 offline interface languages. English is the first-launch
default. Existing SUMUWW artwork is retained.

Extract the complete Windows ZIP and run `SUMUWW-Wallet.exe`. Python is included.
Data is stored separately in `%LOCALAPPDATA%/SUMUWW/Wallet-PC`. The full node can
run alongside it. Import an encrypted wallet backup or restore its recovery
words to use an existing address. Originals are never overwritten. Keep both the
encrypted backup and its password. Recovery words are displayed only on request.

This wallet synchronizes and validates the chain locally with core 0.57.47. It
does not offer mining controls or depend on a remote server to sign payments.
It is not a lightweight/SPV client. Initial synchronization requires peers and
storage for the blockchain. Settings allows adding a reachable peer address.

Before sending, inspect the complete recipient, amount, fee and total in the
confirmation dialog. A confirmed action consumes one expiring quote. No automatic
payment retry is performed. A local submission is not a confirmed transaction.

Valid legacy history through height 8,999 remains usable. From 9,000 inclusive,
old-rule blocks are rejected. The 20% post-PoW proof event, DGW every ten blocks,
original issuance/halvings and asynchronous proof recovery match the full node.

For source execution use Windows Python 3.12 with the pinned dependencies in
`../../PC/Source/requirements.txt`, then `python run.py`. Build with PyInstaller
using `SUMUWW-Wallet.spec`. Desktop tests use disposable regtest wallets only.
The executable is not publisher-code-signed.

## 1.0.8

1 SMW = 100,000,000 yugeon. Automatic fees offer slow, normal and fast presets based on local observations; they do not guarantee confirmation times. You can enter a rate in yugeon/vB manually. Review the final fee and total in SMW before sending. A rejected transaction does not debit your balance.

[Current features in 34 languages](docs/features/index.html).
