# SUMUWW Android 0.6.95 (155)

SUMUWW Android provides an independently validating full node, a personal wallet, CPU mining, peer synchronization and connection proofs. Automatic fees use current pending volume, block capacity and transaction priority. Past block fees are not used. A quiet queue keeps the minimum rate. The preview refreshes; the final confirmation fixes the fee. Observations cover the connected local node, not every node. Multisig and output-lock validation is available for isolated activation tests; public activation is not scheduled. Open More > Help > Documentation for offline Android documentation in all 34 supported languages. English is the default; saved language preferences remain in effect.

Install over the existing org.sumuww.miner app with the same signing certificate. Wallet formats, stored chain history and public-network consensus rules are preserved. The node core supports signed transaction validation/submission, block/transaction/UTXO queries and reorganization state. The Android app has no RPC configuration screen. See [Android node interface](docs/integration/docs/i18n/en/ANDROID.html).

Tests run in the separate .audit package on disposable regtest data. The test fixture is included only in the instrumentation APK. The production APK contains the application modules and offline documents.
