# SUMUWW connection proof upgrade at source block 9,600

Update every validating node and ordinary wallet before block 9,600. This is a block-height deadline, not a guaranteed calendar date. The new required rule applies to proofs whose source block is at least 9,600. Earlier valid proofs and chain history remain valid. Proof absence never blocks ordinary PoW mining or block acceptance. Equal-work branch selection can differ on old versions; do not keep operating an old validating client after activation.

The existing beacon, 20% event probability and three-witness sampler remain unchanged. After activation, each candidate supplies a signed activity response bound to the source, target, recent round and nonce. More than two thirds of the PoW-anchored beacon generation must approve the complete responder list they independently observed. Validators recompute the sampled witnesses from that certificate. The certificate proves this quorum's observations, not independent human ownership or universal Internet reachability. Byzantine-quorum control and identity concentration remain security assumptions.

Before activation, old proof rules remain in force. Once activated, unfinished old jobs may move to a newly certified activity round while preserving their exact original block pair and archiving earlier witness messages and replies. Missing upgraded quorum members or a missing target producer can still delay completion. Failed jobs back off up to 15 minutes and retain their next retry across restart. All history exposes pending phases and witness reply counts. No private key or signature material is returned by the progress API.

Multipart messages are limited to 16 MiB each, 64 MiB of declared concurrent payloads and 120 seconds total duration. Inventory sync pages the complete list without limiting the discovered candidate population.

Versions: Windows node 0.57.48; Android node 0.6.96 (156); Windows wallet 1.0.8; Android Wallet Current 1.1.7 (18); P2P Full and Light 0.3.5. Explorer 0.4.11 fixes wrapped navigation and locale formatting; it remains a read-only chain browser. English remains the default. All 34 languages include directly authored update notices and new interface labels. No third-party translation service was used. Launchpad work is excluded.

Verification uses disposable test-chain data and isolated peers. No public trade, live database migration or physical-phone installation is claimed. Public completion of the nine previously pending jobs is not established by these tests. Matching releases must be distributed and users must install them before the activation height. Download matching source and packages from https://github.com/jack-cal/SUMUWW/releases.

