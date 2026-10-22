> Automatic beacon recovery: PC 0.57.34 / Android 0.6.84. Read [BEACON_RECOVERY.md](BEACON_RECOVERY.md) for compatibility and verification limits.

> Updated height-9000 implementation: read [UPGRADE_9000.txt](UPGRADE_9000.txt). Earlier release notes below describe the original source.

# SUMUWW Independent Coin

<!-- current-links-9000 -->
## 2026-10-22 · 9000 · 20% · DGW/10

Valid blocks through 8999 remain usable, including those sent together with an invalid later suffix. From 9000, every block needs a producer commitment. DGW uses 24 preceding blocks and recalculates at 9000, 9010, 9020…; intervening blocks keep the parent difficulty. The target interval remains 600 seconds. Connection events are random with probability 20%. Three discovered identities sign after PoW; mining and block acceptance do not wait for signatures. Cumulative work takes priority; valid, nonconflicting connections break work ties, followed by the smaller tip hash. Late evidence can change a tie. See the exact implementation and limitations below.

[Current protocol / exact format / limitations](CONNECTION_PROOFS_9000.html)
<!-- /current-links-9000 -->


SUMUWW has its own genesis, transaction history and proof-of-work consensus. Nodes independently validate transactions and blocks and select the chain with the greatest valid cumulative work.

## Coin documents

- [Whitepaper](WHITEPAPER.md)
- [Protocol specification](SUMUWW_PROTOCOL_SPEC.md)
- [Consensus comparison](docs/CONSENSUS_BASELINE.md)
- [Mining rewards and confirmations](docs/MINING_AND_CONFIRMATIONS.md)
- [P2P protocol](docs/NETWORK_PROTOCOL.md)
- [Coin promotion and registration](docs/COIN_PROMOTION_AND_REGISTRATION.md)

## Separate documentation

[PC program documentation](programs/PC/README.md)
