SUMUWW Explorer 0.4.11

Windows application ZIP: extract everything and run start-explorer.cmd (or SUMUWW-Explorer.exe).
The launcher opens http://127.0.0.1:8770 in your browser. If an explorer is already
running there, it opens that instance instead of reporting a duplicate-port error.
Double-clicking the packaged EXE also opens the browser. No Python is required.
Use --no-browser to run the EXE without opening a browser.
Source ZIP: requires Python 3.10 or newer. Install PDF dependencies first: python -m pip install -r requirements.txt.
The source launch script can use this workspace's existing Python runtime, or Python on PATH.

Command line:
  python server.py
  python server.py --database "C:\path\to\node.sqlite" --port 8770

Features:
  Block height/hash, transaction ID and SUMUWW address search.
  Active-chain block/transaction details, input/output links, fees and confirmations.
  Address transaction history, confirmed/available/immature balances, and unspent outputs.
  Local mempool, pagination, 34 bundled interface languages, and responsive browser UI.
  Transaction history filters: all, mining rewards, and ordinary transfers.
  Click the total/reward/ordinary counts to open the matching transaction list.
  Address-relative received outputs, spent inputs and net change (including change outputs).
  Last block timestamp, source read time and elapsed block age, shown separately.
  Local difficulty/interval/transaction charts for 24, 144 or 2,016 recent blocks.
  Raw block and transaction binary downloads; Merkle inclusion proof view/download.
  CSV exports for blocks, confirmed address history and the selected statistics sample.
  Periodic refresh every 15 seconds while the page is visible.

Data handling:
  Reads the selected SUMUWW node.sqlite using SQLite mode=ro and query_only.
  Uses a separate data/explorer.sqlite search index. The source database is never written.
  Active-chain reorganizations remove displaced records from the explorer index.
  Wallet files, passwords, keys, peer connections and mining settings are not accessed.
  This explorer does not mine, start a node, sign transactions or broadcast data.
  The node must synchronize independently for its stored blockchain to stay current.
  Block timestamps are shown in the browser's local timezone.
  Available balance uses coinbase maturity at the next block height and excludes
  confirmed outputs spent by transactions in this node's local mempool.
  Pending received outputs are displayed separately, not added to available balance.
  Pending outputs already consumed by another local mempool transaction are excluded.
  Address view lists up to 100 UTXOs; transaction history is paginated.
  Transaction inputs and outputs describe the stored record; the explorer is not
  an independent consensus validator or a global network connectivity monitor.
  Only the selected node's active chain is displayed, not stored side branches.
  The UI retries if the source snapshot changes between the page summary and detail.
  A failed refresh never publishes a partially updated index. Failed reads hide stale UI numbers.
  New block bytes are checked against their indexed hash, parent and transaction Merkle root.
  An unchanged tip avoids scanning/reindexing the full historical chain on every refresh.

Access:
  Listens on 127.0.0.1 only. This URL is available on this PC, not publicly online.
  Public hosting is not configured. Running it does not open firewall ports.
  No cloud services, analytics, CDN scripts or external fonts are used.
  Stop the explorer with Ctrl+C in its console.
  Only one process may own an index. A second instance requires a different --index and --port.
  All downloads are local; no external services are contacted.
  Download controls use the displayed data snapshot. If source data changes, refresh
  the page before retrying a rejected download (snapshot_changed). Unchanged reads
  retain the snapshot identifier. Unknown Merkle-proof formats are rejected.
  CSV buttons export up to 1,000 recent blocks/address transactions; API limit is up to 10,000.
  Address CSV supports offset for further pages. Pending transactions are not included in address CSV.
  Statistics CSV includes the complete selected sample, up to 2,016 blocks.
  Address received/spent totals describe outputs/inputs. Received totals can include change;
  net change is received outputs minus spent inputs, not a separate transfer amount.
  If pending inputs cannot be resolved, spent/net amounts are unknown rather than zero.
  Difficulty charts are relative to SUMUWW's initial target, not Bitcoin difficulty 1.
  Block timestamp differences can be negative; graphs preserve the stored values.
  Merkle proofs establish TXID inclusion in the included header, not finality, proof of work,
  transaction signature validity or witness-data verification.
  Verify a downloaded proof offline without reading a node DB:
    SUMUWW-Explorer.exe --verify-proof "SUMUWW-proof-....json"
  The explorer does not observe peer synchronization, so it does not label stored data as globally current.
  A missing or corrupt source is reported without creating or repairing the source database.
  Unknown/corrupt index files are refused; choose a new --index path to build a fresh index.
  If the default port is busy, close the other explorer or use --port 8771.

Checks:
  python -B -m unittest -v test_explorer.py
  node --test test_ui.cjs
  Tests use isolated synthetic records to exercise indexing, not consensus acceptance.
  UI unit tests use a DOM/fetch fixture; actual browser checks are recorded separately.
  To build an EXE, install PyInstaller in your build environment and run build-windows.cmd.

Source codecs:
  vendor/sumuww contains the minimal block/transaction/address codecs and their
  dependencies copied from SUMUWW Windows source v0.57.20. See vendor/LICENSE.

Language assets:
  33 language options: Korean, English, Japanese, simplified/traditional Chinese
  (Taiwan and Hong Kong), French, Spanish, Portuguese, German, Italian, Russian,
  Arabic, Swahili, Hindi, Indonesian, Vietnamese, Turkish, Thai, Bengali, Urdu,
  Polish, Dutch, Filipino, Tamil, Czech, Danish, Finnish, Greek, Norwegian,
  Swedish, Serbian and Mongolian (Cyrillic). Language choice is saved locally.
  Arabic/Urdu use right-to-left layout. Hashes and chart axes remain left-to-right.
  Additional translations were prepared with Google Translate at build time;
  technical identifiers remain unchanged. Runtime uses bundled static assets.
  Rebuild languages.js offline from included locales: python prepare_languages.py
  The optional --translate-missing flag contacts Google only for missing locale files or keys.

Page navigation: current/total page numbers, clickable first/last/nearby pages, and a direct page-number input. The selected transaction kind is preserved.

Analytics added in 0.4.0:
  Fees: smallest units/vB (100,000,000 units = 1 SMW), ancestor-package rates,
  25th/50th/90th percentile estimates from local pending + up to 200 confirmed
  ordinary transactions. No inclusion time guarantee; zero fees may be valid.
  Missing input amounts are unknown, never fabricated zero fees. Mempool sizes,
  fee buckets, known fee totals and unresolved counts describe this node only.
  Related transactions: direct input parents, spending children, pending ancestor
  and descendant packages. This does not identify owners or verify RBF support.
  Mining: 24/144/2016-block work/time hash-rate estimates, claimed rewards,
  known fees, payout-address distribution, current/next difficulty and changes.
  Payout addresses do not establish miner/pool identity; shares can overlap.
  Block comparison: the explorer observes its source every 3 seconds while running,
  even with its browser closed. It saves a conservative fee-package projection
  before indexing the next block, then compares ordinary TXIDs actually included.
  This is not the miner's template or a consensus/signature/sigops validator.
  Old blocks without a prior observation have no comparison data. Differences
  can reflect timing, local visibility or policy, not misconduct. Reorg cleanup
  removes orphaned observations along with displaced indexed blocks.
  Transaction filters: UTC dates, inclusive height and output-total bounds,
  height/time/amount/fee/rate sorting, ascending or descending. Paging and export
  preserve filters. Output total includes change, not just a payment amount.
  Address period analysis: opening/closing balance, exact received/spent/net,
  balance after each transaction and a chart grouped into up to 512 height buckets.
  Set maximum height to obtain the balance at a past block. Includes immature
  rewards, excludes pending transactions and the unspendable genesis reward.
  Address date filters map to a contiguous height span, because block timestamps
  can move backward; they do not prove a wall-clock balance at that instant.
  PDFs: transaction receipt, filtered transaction report, address period report.
  Each states local chain tip, read time, scope and included/total row counts.
  At most 10,000 rows per report/export. These are local records, not signed
  payment certificates, ownership proofs, legal receipts or finality guarantees.
  PDFs use subset-embedded Windows fonts, without distributing the font files.
  Source on systems lacking these fonts uses English PDF labels as stated in-file.
  New PDF runtime libraries: ReportLab, Pillow, python-bidi, arabic-reshaper,
  uharfbuzz. Their notices are included in THIRD-PARTY-NOTICES.txt.
  Run all isolated reader/analytics tests: python -B -m unittest discover -p "test_*.py"
  PDF tests also need pypdf; it is not required to run the explorer.

Fixes in 0.4.2:
  Include and freeze the DGW module required by mining analysis from height 8064.
  Detect the current SUMUWW data directory and SUMUWW_DATA_DIR, while preserving
  existing DORA data locations and active-node marker compatibility.
  The node, mining process, chain database and wallet settings are not changed.

Verification for 0.4.2:
  83 isolated reader/HTTP/analytics/PDF/path tests and 40 UI-code tests passed.
  Activated-difficulty regression covers actual heights 8063 and 8064.
  62 requests against the exact new EXE on the actual local height-8533 chain
  passed, including raw records, proof verification, 4 PDF languages, CSV,
  address balances against read-only source UTXOs and loopback request rules.
  Browser checks covered searches, copy, pagination, filters, analytics,
  English/Arabic/Korean language changes, address history and actual downloads.
  Original EXE failed with only the new SUMUWW data path; this EXE succeeded.
  Bytecode for server, analytics, reports and DGW matched this source.
  Local mempool was empty; nonempty cases were exercised in isolated tests.

Changes in 0.4.5:
  Display and search witness-v0 32-byte P2WSH output addresses used by HTLCs.
  Repair missing addresses when opening recognized older explorer indexes.
  The address codec and migration are read-only with respect to the node chain.
  Showing an address or a Merkle inclusion proof does not verify the contract's
  spending conditions, a global chain tip or cross-chain completion.

LANGUAGE SETTINGS
First launch defaults to English. Use the language selector for 34 offline catalogs. An explicit browser language choice is retained. Missing/invalid settings fall back to English.

Current consensus compatibility: the expected difficulty calculation supplies the ten-block DGW schedule from height 9000. The bundled read-only core is based on 0.57.34; the currently published full nodes are Windows 0.57.40 and Android 0.6.89. The consensus rules read by this Explorer are unchanged. See CURRENT_GUIDE.md for component versions, publication status and proof scope.

UPGRADE AT HEIGHT 9000
Valid legacy blocks through 8999 remain usable. Old-rule blocks at 9000 inclusive and above are rejected by upgraded nodes. Update miners and validating nodes. See CURRENT_GUIDE.md.

## 0.4.11

The explorer shows fee rates in yugeon/vB. When the local node has recorded a transaction replacement, the transaction page links to the replacement. Confirmed chain records take precedence; local replacement history is limited.

[Current features in 34 languages](docs/features/index.html).
