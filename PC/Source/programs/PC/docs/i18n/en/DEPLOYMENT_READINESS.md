# Deployment readiness and failure handling

This is a program operating guide, not a change to SUMUWW consensus or a promise of Internet-scale reliability. The developer need not operate a central control service. Each node independently verifies its ledger and applies local resource limits. Peers must actually exist and be reachable; discovery cannot create connectivity through every firewall or NAT.

## Existing protections checked

- Eight direct peer sessions in total, with bounded incoming admission and outbound reservation. Excess connection attempts are rejected instead of accumulating unlimited sessions.
- Per-peer allowances for request work, transaction hints, validation bytes and outgoing bytes. These are protocol allowances, not a fixed operating-system CPU percentage or a universal memory-use guarantee.
- Frame, handshake, response and write deadlines; incomplete or non-reading peers cannot wait forever. Invalid-data cooldowns use actual remote IPs. Healthy existing sessions sharing an IP are retained; new sessions sharing a blocked NAT IP can still be affected.
- At most 1,000 pending transactions and 4,000,000 serialized bytes. Full-pool rejection does not confirm or debit a rejected transfer. The limit is local node policy, not total network transaction capacity.
- An unverified backup does not suspend mining when a fresh verified anchor remains. Normal live block receipt preserves mining on the last validated tip until the new block is fully checked. No fresh verified anchor means mining waits; a user stop remains terminal.
- Validation is required before ledger activation. PoW, contextual difficulty, reward amounts, maturity, signatures and spending constraints are not bypassed during overload or recovery.
- Block storage, UTXO changes and selected-tip updates commit atomically. Restart verifies stored state. Abrupt-process-loss tests do not prove every physical power-loss, faulty-disk or external-filesystem condition.

## Evidence

The deployment-focused suite passed 113 cases with no failures, errors or skips. It includes two new cases and reruns relevant prior overload, synchronization, RPC, mempool, cache and mining-wait checks.

- 32-node local ring, eight node restarts, 32 valid blocks: all nodes converged on the same tip/UTXO commitment, persisted-state verification and database integrity checks passed, and owned sessions/tasks closed.
- Process exit before commit at three points: block saved, UTXOs saved, tip saved. Confirmed state remained unchanged, partial blocks did not become confirmed, and mining resumed after reopening.
- Existing 32/64/128-attempt admission spikes, partial handshakes/frames, non-reading peers, bounded request responses, honest-peer survival and shutdown/reconnect checks were rerun.
- 512 legal header requests were throttled while honest block relay continued. 1,000 signed transaction delta-relay and full-block confirmation checks passed.

These are isolated local fixtures, not independent public Internet participants. There is no assertion of a tested million-user capacity, a sustained multi-day duration, real 5G availability or physical power-loss recovery.

## Symptoms and response

| Symptom | Safe response |
|---|---|
| Connected peers are zero | Preserve the wallet/chain. Check Internet permission and automatic discovery, then optionally provide a reachable operating peer. Do not create a new wallet to repair networking. |
| Connections exist but mining is waiting | Check validated synchronization/freshness, not just socket count. A raw TCP connection does not prove a usable chain. |
| Pending pool is full | A refused transfer is not confirmed. Check transaction status before retrying; avoid repeatedly generating payments for the same intended transfer. |
| Connections or responses degrade under load | Inspect the bounded node counters and peer state; keep protocol limits enabled. No extra coin issuance or validation bypass is an acceptable workaround. |
| Application terminated unexpectedly | Restart and allow stored-state validation/synchronization. Do not delete wallet or chain files. If validation fails, retain them for diagnosis and recover from a verified backup rather than overwrite them. |
| A software defect is reproduced | Publish a compatible corrective release with tests and release notes. Each user chooses whether to update; there is no remote administrator key to force an update. Consensus changes require separate compatibility analysis. |

For optional authenticated local RPC, `getnetworkinfo` exposes peer/resource counters, `getblockchaininfo` includes synchronization readiness, and `getmempoolinfo` exposes local pending capacity. Keep RPC tokens private; do not publicly expose the RPC port to diagnose ordinary P2P connectivity. General users can view node and synchronization status in the application.

## Rollout boundary

Start with a bounded voluntary distribution, verify actual independent Internet paths and collect reproducible failure reports before increasing exposure. This is a release practice, not a central operator role or a condition built into coin consensus. Existing tests reduce known failure risks; they cannot eliminate every deployment failure. Physical phone background throttling, physical ASIC compatibility and long-term public load remain separate unverified items.
