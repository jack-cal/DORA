# SUMUWW PC program

<!-- current-links-9000 -->
## 2026-10-22 · 9000 · 20% · DGW/10

Valid blocks through 8999 remain usable, including those sent together with an invalid later suffix. From 9000, every block needs a producer commitment. DGW uses 24 preceding blocks and recalculates at 9000, 9010, 9020…; intervening blocks keep the parent difficulty. The target interval remains 600 seconds. Connection events are random with probability 20%. Three discovered identities sign after PoW; mining and block acceptance do not wait for signatures. Cumulative work takes priority; valid, nonconflicting connections break work ties, followed by the smaller tip hash. Late evidence can change a tie. See the exact implementation and limitations below.

[Current protocol / exact format / limitations](../../CONNECTION_PROOFS_9000.html)
<!-- /current-links-9000 -->


SUMUWW PC program · 0.57.33

Extract the Windows executable package and run SUMUWW.exe. Keep the shared runtime and documents beside it.

Run SUMUWW-node-manager.exe to independently discover SUMUWW peers through IPv4/IPv6 DHT, LAN announcements and P2P address exchange. It maintains its own non-mining P2P connections, accepts incoming connections and shows the currently responding peers, their TCP addresses, returned block heights, connection directions and observed tip updates. It uses its own TCP listener on port 18446 and announces only contacts on its actual bound public interfaces; it does not change firewall rules. An incoming TCP source port is not treated as a peer's listening port. Disconnected peers and failed address attempts do not count as current connections. Refresh requests another discovery attempt; existing connections continue automatically.

The manager does not read the miner's connection list, RPC, wallet or chain database, and does not mine or send transactions. It advertises only its fixed genesis as owned data, answers requests for that data and checks returned tip hashes, PoW and Merkle roots. Those checks do not replace full contextual chain validation. Peer process nonces group observed address aliases but are not authenticated identities or a count of people. Discovery is not a complete network census, and remote mining status is not observable.

Encrypted wallet creation, opening, seed recovery, backup and restore; balances, fees, signed transfers and transaction history; mining, pause/resume, node discovery, synchronization, RPC/API and on-demand node checks.

[RPC/API](docs/i18n/en/RPC_API.md) · [Network](docs/i18n/en/NETWORK_RUNBOOK.md) · [Capabilities](docs/i18n/en/CAPABILITIES.md)

[CPU / GPU / ASIC](docs/i18n/en/MINING_DEVICES.md)

[Deployment readiness and failure handling](docs/i18n/en/DEPLOYMENT_READINESS.md)
