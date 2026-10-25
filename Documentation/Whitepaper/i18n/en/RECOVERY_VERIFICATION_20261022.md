> Historical evidence for PC 0.57.34 / Android 0.6.84, 22 October 2026. These are not new tests of 0.57.40 / 0.6.89.

# Beacon recovery verification

Windows 0.57.34 / Android 0.6.84 (144), 2026-10-22.

## Completed checks

- Ten new recovery regression cases passed: historical proof preservation,
  fresh-group threshold output without old shares, invalid predecessor/round/
  timing rejection, incomplete or forged readiness rejection, stale template
  handling, branch-specific generation selection, legacy overwrite rejection,
  invalid encrypted dealer identification, isolation from failed old jobs, and
  recovery from an unavailable prepared proposal.
- The combined PC regression run passed 36 executions (28 distinct cases;
  eight original cases were also discovered through an imported test class).
  It includes the original proof/transport, late discovery, 20% probability,
  preserved issuance and DGW/10 checks. This is a targeted regression run, not
  a rerun of the preceding release's entire UI or security audit.
- Two numeric activation-prefix cases passed with an independently mined
  height-8999 regtest snapshot: the valid old prefix survives an invalid
  height-9000 continuation and synchronization resumes with valid new blocks.
- A real loopback TCP fixture used eight distinct node identities in separate
  processes, with seven simultaneously present during replacement. One node
  acknowledged probes but withheld DKG data; the attempt expired and a valid
  three-member setup was prepared from four discovered contacts.
- All original beacon shares were then withheld. Three new participants
  prepared a new key, seven nodes accepted its PoW-anchored generation, and a
  further complete connection proof was produced using it.
- With witness replies delayed eight seconds and the old beacon unavailable,
  five local regtest blocks were mined in approximately 0.031 seconds. This
  measures independence from the reply wait, not public-network mining speed.
- Four original processes were stopped. The three replacement nodes remained
  connected and synchronized. A restarted replacement and a late eighth node
  verified the historical and replacement proofs. The final four nodes agreed
  at height 43, with two complete proofs, the same tip and UTXO commitment,
  and successful SQLite integrity checks.
- Windows executables built successfully and passed six packaged checks with
  temporary databases: CLI/version, offline public-profile mining guard,
  wallet/mine/send, encrypted backup/restore, two-daemon block/transaction relay,
  and the portable launcher without a Python installation on PATH.
- Android built successfully with both configured native ABIs. The final APK
  was signed through the existing signing lineage; its current certificate
  SHA-256 is `8481abe8acb2fbc935f824008fa54cd78e790bebbb5795f80604234ee1b4cf4d`,
  matching 0.6.83. The four beacon source modules match the PC copies exactly.
- A connected Samsung SM-S928N running Android 16 passed 29 Python cases in
  two instrumentation tests: 27 connection-proof/recovery/DGW cases and two
  numeric 8999/9000 prefix cases. These ran in a separate audit application,
  using the Android native cryptography adapter and isolated test databases.
  The first prefix attempt lacked its synthetic height-8999 fixture; after
  copying that fixture, both prefix cases passed. No source change was needed.
  The temporary audit applications were removed after collecting the results.

The successful process run is retained in `verification/eight-node-recovery.json`
in the local delivery. Earlier failed fixture runs were retained in the work
directory: one disconnected all replacement nodes by stopping their sole test
relay; another incorrectly required unmined proposals to match; another stopped
PoW before an intermediate generation's recovery spacing had elapsed. The final
fixture preserves a replacement-to-replacement path, tests agreement after PoW
commitment, and continues ordinary mining through recovery windows. The
unavailable-prepared-proposal bug found during these runs has a regression test.

## Limits and deployment status

The tests ran on this Windows host and a connected Android phone, using isolated
local chains. The phone tests exercised protocol and native runtime behavior;
they were not a full UI interaction audit. Directly importing the Android-only
secp256k1 adapter on Windows is not a valid device test. No installed production
wallet or live chain database was replaced during those isolated tests. The
phone's original application remained at version 0.6.82 (142) during that stage.
The subsequent local deployment installed Windows 0.57.34 and Android 0.6.84
over the existing applications, retaining their wallet and chain data.

The PC difficulty label now shows the pending height-9000 transition before it
activates, instead of showing only the current per-block rule. All 34 catalogs
include that transition text; four targeted UI/catalog tests passed, including
the cadence label at heights 8998, 8999, 9000, 9009 and 9010 in every language.
The Windows executable version resource now matches 0.57.34, and the build
rejects a stale resource version. The packaged Windows checks passed again.
Icons, button layout, wallet implementation, monetary rules and difficulty
implementation are unchanged.

There is no claim of a multi-day public Internet trial, public height-9000
activation, independent cryptographic audit, complete worldwide discovery,
arbitrary-adversary DKG liveness, or recovery of a lost old threshold secret.
Incomplete old jobs can remain incomplete. The existing equal-work proof rule
still permits late evidence to alter a tie; valid greater cumulative work wins.

Replacement records require upgraded validating software. The earlier binaries
reject these new setup contexts. Historical records remain valid in the updated
implementation; update participating validators before the activation rollout.
Windows 0.57.34 and Android 0.6.84 are published with this verification record. Publishing a normal release does not extend the verification scope stated above.

See [the recovery protocol](BEACON_RECOVERY.md) for exact transitions and limits.
