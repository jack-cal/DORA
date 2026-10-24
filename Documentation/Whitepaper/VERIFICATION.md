# Whitepaper v2.2 verification and limits

Reviewed on 24 October 2026 against repository base
`da1eee4fb52dcada8b1ba56289ff3d623a9e13ca`, with documentation edits after that commit.
Application builds remain PC 0.57.40 / Android 0.6.89. Whitepaper 2.2 is a separate document release; earlier release posts and attachments remain unchanged.

## Evidence used

- Inspected producer-job scheduling, signed participant probes, beacon event selection, witness sampling, persisted replies, receipts and job counters in both current full-node source trees.
- Compared issuance, integer rounding, genesis exclusion, maturity, DGW activation/cadence and HTLC activation descriptions with current source and targeted regression checks recorded in DOCUMENT_REVIEW.json.
- The 24 October connection repair recorded 84 regression executions, final PC checks (5 availability/restart/corruption and 4 history/UI checks), 5 Android-source host checks and 6 frozen PC smoke checks. Shared test re-executions are not distinct cases. See the [published repair record](https://github.com/jack-cal/SUMUWW/blob/da1eee4fb52dcada8b1ba56289ff3d623a9e13ca/Documentation/CONNECTION_PROOF_REPAIR_VERIFICATION.md).
- A mixed-witness source test completed, stored and verified a proof using a PC 0.57.40 producer with ordinary-wallet PC 1.0.2 and Android 1.1.2 responders. It used real signatures and an in-memory relay on the host, not physical Android devices.
- The packaged Explorer 0.4.6 indexed 9,177 active blocks through height 9176, 9,177 reward transactions and 64 ordinary transactions in a read-only snapshot on 24 October. A TXID inclusion proof verified, packaged app/UI files matched source and 43 UI tests passed. These findings concern transaction history, not completed connection proofs.

## Publication, installation and test scope

This edition accompanies [whitepaper 2.2](https://github.com/jack-cal/SUMUWW/releases/tag/whitepaper-v2.2-en) and the
[documentation release](https://github.com/jack-cal/SUMUWW/releases/tag/docs-20261024-r1). The current suite has full nodes
PC 0.57.40 / Android 0.6.89, ordinary wallets PC 1.0.2 / Android 1.1.2,
Explorer 0.4.6 docs-r3 and P2P Full/Light 0.3.0 docs-r2. Document revisions keep
their existing executable versions and tested runtime bytes. Earlier package
digests remain attached to their original releases. DOCUMENT_REVIEW.json is
the earlier local review snapshot; it is not the current publication manifest.
The desktop production full-node replacement remains pending. Publication
does not start, install or replace an operating application.

No new production transfer, mining run, physical Android run or Internet endurance
test is claimed by this documentation review. Past snapshots are not live counts.
The nine old selected jobs had valid beacon/selection records but no complete
stored proof at the recorded inspection. Their old store lacked per-job error
diagnostics, so the exact failure of every individual job cannot be established.
Isolated completion does not prove completion on the operating public network.

Worldwide discovery, omission resistance, malicious-participant DKG security and
uninterrupted availability are not established. Missing original witnesses can
leave selected old jobs incomplete indefinitely. Existing valid history, wallet
keys and signature locks are retained. No private wallet, key, chain database or
raw device/network log is included in this document archive.

[Historical recovery verification, 22 October](RECOVERY_VERIFICATION_20261022.html)
records only the earlier PC 0.57.34 / Android 0.6.84 tests.
