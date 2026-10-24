# Connection-proof repair — PC 0.57.40 / Android 0.6.89

Release preparation and verification, 24 October 2026. Publication status and uploaded assets are recorded on the [PC 0.57.40 release](https://github.com/jack-cal/SUMUWW/releases/tag/pc-v0.57.40) and [Android 0.6.89 release](https://github.com/jack-cal/SUMUWW/releases/tag/android-v0.6.89).
Earlier release and publication documents remain historical records for their named versions.

## Production observations (read-only)

At 16:02:38 KST, height 9168: 12 active beacon setup records, 54 local lottery jobs,
45 nonselected finished lotteries, 9 selected pending jobs, 0 selected completed
jobs and 0 complete proofs in storage. The earlier 11 setup records increased
as mining continued. One setup can serve several jobs: setup height 9091 served
selected source heights 9093, 9094 and 9100. The 9 selected jobs' beacon outputs
and saved candidate selections were cryptographically verified. Subtracting
setup records from selected-job counts is not a valid completion calculation.

The old runtime sampled historical contacts without a fresh availability check.
All 9 selected jobs included a witness outside the latest beacon group. This
is consistent with unavailable participants, but does not prove that all nine
failed for that exact reason: the old store has no per-job failure diagnostics.
The offline-contact failure was independently reproduced with real signatures
in an isolated fixture. The old code failed; the corrected code completed,
stored and verified the proof with the same discovered inventory.

## Repair and compatibility

New jobs probe the entire discovered inventory using authenticated nonce echoes,
including relayed participants, then select three responsive identities using
the verified beacon. Silent contacts are retained for later attempts. This is
a local availability policy, not a consensus membership or admission rule.
Existing selected jobs preserve their exact message and three witnesses.
Valid partial replies are stored immediately and reused after failures and
restarts. Invalid saved replies are discarded and requested again. Phase,
missing-witness and error details persist. PC public history labels local job
outcomes separately from stored complete proofs. All 34 translations were
authored directly, without an external translation service.

The attachment format, 20% event, three-signature validation, signature locks,
PoW, chain choice, wallet format and existing history are unchanged. Existing
v2 peers understand the probe. Old jobs may remain pending until their original
witnesses return. A new participant can also go offline after responding.
Ordinary wallets keep the prior repair versions, PC 1.0.2 / Android 1.1.2;
this producer-job repair does not require rebuilding those ordinary wallets.

## Verification and limits

84 regression test executions passed (including shared fixture re-executions).
Final additional checks: five real-signature availability/restart/corruption
tests on PC, the same five against Android sources using the host crypto backend,
and four PC browser tests including counters in all 34 languages. PC frozen
executable smoke checks, source/archive consistency, APK signature and version,
document links and whole-folder checksums are recorded in the matching JSON.
The production node is not used for test transfers or test mining. No wallet,
private identity key, chain database or device log is distributed. Physical
Android execution and long-running Internet completion are not verified by
these host tests. The repaired production application must be started before
its new diagnostics or proof behavior can be observed there.
