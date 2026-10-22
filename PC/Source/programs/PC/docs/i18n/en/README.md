# SUMUWW PC program

<!-- current-links-9000 -->
## 2026-10-22 · 9000 · 20% · DGW/10

Valid blocks through 8999 remain usable, including those sent together with an invalid later suffix. From 9000, every block needs a producer commitment. DGW uses 24 preceding blocks and recalculates at 9000, 9010, 9020…; intervening blocks keep the parent difficulty. The target interval remains 600 seconds. Connection events are random with probability 20%. Three discovered identities sign after PoW; mining and block acceptance do not wait for signatures. Cumulative work takes priority; valid, nonconflicting connections break work ties, followed by the smaller tip hash. Late evidence can change a tie. See the exact implementation and limitations below.

[Current protocol / exact format / limitations](../../../../../CONNECTION_PROOFS_9000.html)
<!-- /current-links-9000 -->


SUMUWW PC program · 0.57.33

Extract the Windows executable package and run SUMUWW.exe. Keep the shared runtime and documents beside it.

Encrypted wallet creation, opening, seed recovery, backup and restore; balances, fees, signed transfers and transaction history; mining, pause/resume, node discovery, synchronization, RPC/API and on-demand node checks.

[RPC/API](RPC_API.md) · [Network](NETWORK_RUNBOOK.md) · [Capabilities](CAPABILITIES.md)

[CPU / GPU / ASIC](MINING_DEVICES.md)

[Deployment readiness and failure handling](DEPLOYMENT_READINESS.md)
