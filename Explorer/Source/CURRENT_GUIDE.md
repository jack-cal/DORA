# SUMUWW Explorer 0.4.10

Run start-explorer.cmd after extracting the complete Windows ZIP. The explorer
reads a local SUMUWW node database in read-only mode and writes only its own,
separate index. Use --database to select another node.sqlite. It does not
independently synchronize or validate the chain. Displayed history is the
selected node's active chain, including rewards and transactions from all nodes.
Address searches narrow the view to that address; they do not limit the main
block or transaction lists to your wallet.

## Current versions and publication status

Full-node releases are Windows 0.57.46 and Android 0.6.95. Ordinary wallets are
Windows 1.0.6 and Android Wallet Current 1.1.6. They retain connection recovery and
synchronization repairs and can respond to authenticated witness probes.

Explorer executable 0.4.10 includes block reward components, yugeon fee-rate
labels, recorded replacement links and revealed spending conditions. Download:
https://github.com/jack-cal/SUMUWW/releases/tag/explorer-v0.4.10
P2P Full/Light are 0.3.4, and the current English whitepaper is 2.2.
Earlier release posts and assets remain unchanged. Publication does not replace
an operating installation. See the suite's current release and installation guide.

## Proof scope

The explorer's proof download is a TXID Merkle inclusion proof for a transaction
inside a block. It is not the asynchronous connection proof created by three
witnesses, and the explorer currently has no connection-job completion counter.
Use the full node's public history/status for those separate job/proof counters.
An inclusion proof does not establish consensus validity or irreversible finality.

## Trading applications

P2P Full and Light are separate applications. Both require a synchronized
SUMUWW node and HTLC activation at height 9100. Full also requires synchronized,
unpruned Bitcoin Core with txindex. Light verifies Bitcoin headers and proofs
and depends on available honest servers for complete histories. An advertisement
or reservation does not transfer funds.

## Verification and limits

In the earlier 0.4.6 check on 24 October 2026, the Explorer indexed all 9,177 active
blocks through height 9176, including 9,177 reward transactions and 64 ordinary
transactions. Reward outputs covered 59 distinct addresses. Genesis, height
9000 and the current tip were queried through its local HTTP API, and a TXID
inclusion proof verified. The node database was opened read-only; the test index
was separate. All 43 JavaScript UI tests passed. Packaged app modules and UI
files match source. These are point-in-time checks, not continuous operation.

All 34 offline UI languages and saved preferences are retained. Current 0.4.10
packaging checks compare the compiled application modules with their source.
The guide was written directly without an external automatic translation service.
Earlier 0.4.6 execution tests remain historical.

## 0.4.10

The explorer shows fee rates in yugeon/vB. When the local node has recorded a transaction replacement, the transaction page links to the replacement. Confirmed chain records take precedence; local replacement history is limited.

[Current features in 34 languages](docs/features/index.html).
