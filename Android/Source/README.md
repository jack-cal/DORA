> All blocks browser: PC 0.57.38 / Android 0.6.88. See [RELEASE_NOTES.txt](RELEASE_NOTES.txt). Browse the full validated local chain; mining progress remains separate.

> Automatic beacon recovery: PC 0.57.34 / Android 0.6.84. Read [BEACON_RECOVERY.md](BEACON_RECOVERY.md) for compatibility and verification limits.

# SUMUWW Android 0.6.88

Valid blocks through 8999 remain usable, including those sent together with an invalid later suffix. From 9000, every block needs a producer commitment. DGW uses 24 preceding blocks and recalculates at 9000, 9010, 9020…; intervening blocks keep the parent difficulty. The target interval remains 600 seconds. Connection events are random with probability 20%. Three discovered identities sign after PoW; mining and block acceptance do not wait for signatures. Cumulative work takes priority; valid, nonconflicting connections break work ties, followed by the smaller tip hash. Late evidence can change a tie. See the exact implementation and limitations below.

[Current protocol](CONNECTION_PROOFS_9000.html)

> Updated height-9000 implementation: read [UPGRADE_9000.txt](UPGRADE_9000.txt). Earlier release notes below describe the original source.

# SUMUWW Android 0.6.88

SUMUWW Android provides an independently validating node, a non-custodial wallet and CPU proof-of-work mining. The phone maintains its own chain data and wallet.

Install the signed APK over the existing app to update. Preserve an encrypted wallet backup and recovery words. Do not uninstall the app or clear its data to perform an ordinary update.

Create, open or recover a wallet through Wallet management. Connect to a compatible peer and synchronize before mining. Review the recipient, amount and network fee before confirming a transfer.

Settings include 34 languages, appearance, node connections, mining protection and notifications. Required consent covers device/background operation and peer communication.

[USER_GUIDE.md](USER_GUIDE.md) · [REGISTRATION_GUIDE.md](REGISTRATION_GUIDE.md)

Node upgrade: exact-template HTLC spends activate at height 9100. The asynchronous connection-proof rules at 9000 and existing ordinary transfers are unchanged. See [HTLC_9100.md](HTLC_9100.md).
