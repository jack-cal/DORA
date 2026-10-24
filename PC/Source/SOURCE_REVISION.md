# PC source snapshot — 0.57.40

Base commit: b5fbc973aa91d3f84cb016878361f8a4d856a16d.
Includes the previous local dependency/documentation repairs and the public-history and connection-proof availability changes in RELEASE_NOTES.txt. This snapshot includes changes after the base commit. The source archive contains SOURCE_FILES.json with exact file hashes and SOURCE_COMMIT.txt with the release commit. Release tag: pc-v0.57.40.

# SUMUWW · 9000 · 20% · DGW/10

Valid blocks through 8999 remain usable, including those sent together with an invalid later suffix. From 9000, every block needs a producer commitment. DGW uses 24 preceding blocks and recalculates at 9000, 9010, 9020…; intervening blocks keep the parent difficulty. The target interval remains 600 seconds. Connection events are random with probability 20%. Three discovered identities sign after PoW; mining and block acceptance do not wait for signatures. Cumulative work takes priority; valid, nonconflicting connections break work ties, followed by the smaller tip hash. Late evidence can change a tie. See the exact implementation and limitations below.

[Current protocol](CONNECTION_PROOFS_9000.html)

Background fresh-key recovery is described in BEACON_RECOVERY.md.
