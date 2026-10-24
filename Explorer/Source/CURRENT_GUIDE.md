# SUMUWW Explorer 0.4.6 — local documentation revision 2

Run `start-explorer.cmd` after extracting the complete Windows ZIP. The explorer
reads a local SUMUWW node database without modifying it. Use `--database` with
the path of another node.sqlite to select it. It does not synchronize a node or
independently validate the chain. Displayed data reflects the selected database.

This docs-r2 package corrects the obsolete copied suite guide. Explorer
executable code remains 0.4.6. The new documentation package is local and has
not been published to GitHub; the existing 0.4.6 release remains historical.

Current local suite: Windows full node 0.57.38; Android full node 0.6.88;
Windows wallet 1.0.2; Android Wallet Current 1.1.2; P2P Full/Light 0.3.0;
Explorer 0.4.6; English whitepaper 2.1. The new wallets include the current
connection recovery and synchronization fixes.

P2P Full and Light are separate applications. Both require a synchronized
SUMUWW node and HTLC activation at height 9100. Full additionally requires
synchronized unpruned Bitcoin Core with txindex. Light verifies Bitcoin headers
and proofs and depends on available honest servers for complete histories.
An advertisement or reservation does not transfer funds.

All 34 offline interface languages and saved preferences are retained.
Earlier Explorer verification results remain historical; no new Explorer
runtime behavior or public-network test is claimed by this documentation repair.
