> **Archived document.** Preserved from the published documentation before consolidation. For current rules and instructions, see https://github.com/jack-cal/SUMUWW/tree/main/Documentation .

# SUMUWW current source revision

## Current source policy: random signature blocks from height 9000

This document describes Windows **0.57.28** / Android **0.6.78** (versionCode 138). Exact-template HTLC spending activates at height **9100**, independently of the unchanged BLS rule at **9000**. Existing mature coins and ordinary P2WPKH transfers remain usable. See [HTLC details](HTLC_9100.md). Download [Windows 0.57.28 / Android 0.6.78](https://github.com/jack-cal/SUMUWW/releases/tag/smw-0.57.28-0.6.78).

From height 9000, each parent/height context selects whether its next block requires BLS signatures with a 10% probability. The input is the network identity, block height and previous block hash, under the `sumuww-random-boundary-block-10pct-v1` domain. The current candidate's nonce and transactions are excluded. Ten percent is an average probability, not a fixed ten-block interval, a preparation deadline or an unbiased randomness guarantee.

Only selected blocks require a complete certificate. The first selected block has `start: null`; each later selected block links to the latest selected ancestor. Ordinary intervening PoW blocks contain neither a certificate nor a split trace. Native PoW/content/transaction checks and the registered-history conflict checks still apply to them. Signatures do not add a PoW work bonus.

The selected team still has three distinct node identities and three distinct observed IP addresses. Discovery and signed replies can be relayed through indirect peers. The responder count and neighbor-observation count are not capped at 1024 and 32. The BLS private signing keys belong to the actual selected nodes; the public block-selection seed is not their private key. The mining service obtains final signatures after valid PoW is found, while the following candidate can be hashed in parallel. Zero signing delay or delivery completed before PoW is not established by this revision.

## Old software, ordinary transfers and joining a branch

| Input received by this source revision | Verification result |
|---|---|
| Unsigned old-software block at a selected height | Reject: complete boundary proof required |
| Unsigned old-software block at an unselected height | Can pass if native rules and registered ancestry also pass |
| Longer branch conflicting with an already registered selected block | Reject: registered connection conflict; claimed extra work does not bypass it |
| Old-wallet transaction spending a mature, valid, unspent common-history output | Verify the owner signature and amounts; can relay and confirm normally |
| Transaction spending a reward existing only on a rejected fork | Reject for a missing/spent input; block-certificate checks are separate from wallet signatures |

Software age alone is not a transaction field or a blanket reason to refuse valid existing coins. A TCP handshake does not establish post-activation block compatibility. A peer that cannot supply the necessary certificate cannot supply that selected block to this revision.

The former every-block-policy database marker can be updated only before any block at or above activation exists, and only when all proof, tail and registration tables are empty. Verified pre-activation blocks, UTXOs, wallets and balances are preserved. A database already using the old policy after activation is refused instead of silently reinterpreting its history.

## Runtime requests, connections and retained addresses

Active discovery objects and their wait events are preserved regardless of how many queries are present. Unowned old-parent queries and idle/finished/cancelled queries are cleaned up. A local discovery with no fresh response ends with an explicit idle error; it does not certify a partial response set or secretly redraw a team.

There is no 512-call limit or default direct-peer count limit, and the address cache has no 128-entry or 64-KiB limit. Failed contacts are removed; healthy alternate connections are protected. Expired retry-suppression entries and completed call records are removed. Local idle retention is `max(60 seconds, socket_timeout * 8, measured_processing_time * 2)`; active send/execution/waiter references are protected. Saved manual preferences remain distinct from the discovery cache. An explicitly supplied CLI `--max-peers` is still an operator option; the application does not set one by default.

Large boundary messages use authenticated `bpart` fragments, with 256-KiB data parts, ordered offsets, a transfer identifier and complete-message digest verification. A whole proof is not limited to 1 MiB. The native `bblock` envelope still uses a uint32 proof-length field, and normal frame/transaction/block limits, DHT round budgets and per-peer traffic quotas remain separate. The observed test sizes are test inputs, not new count limits.

## Verification evidence and scope

The old 0.57.22 core actually mined and accepted an isolated regtest history through height 8999 and unsigned branches through 9111. The last packaged policy rejected its unsigned block 9000. This revision accepted native blocks 9000–9003 on the tested main branch and rejected selected block 9004 without its certificate. The identical block passed with three real private-key BLS signatures. A conflicting private branch and its reward transfer were rejected; an old common-history transaction was accepted and confirmed. Actual TCP tests also rejected the old peer's unsupported selected block. Selection heights vary with the parent hash.

These are isolated native-code/loopback tests at real numeric heights, not a public-network activation, a worldwide census, independent operator proof or a complete 51% defense proof. The original PoW, genesis, issuance, spending signatures and reward maturity rules remain applicable.


[Whitepaper](WHITEPAPER_EN.md) · [Boundary detail](BOUNDARY_V4_EN.md)
