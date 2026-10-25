# SUMUWW Android 0.6.95 · Operasi node

SUMUWW Android 0.6.95 · Node memvalidasi, menyimpan, meneruskan, dan menyediakan data rantai.

## Jaringan dan alamat

Jaringan publik adalah `sumuww`, dengan alias internal `dora`. Periksa hash genesis di bawah. Alamat asli memakai witness v0 P2WPKH dan HASH160 kunci publik secp256k1 terkompresi. Memo atau tag tidak wajib. Tolak jaringan yang salah dan checksum tidak valid. Catat cabang HD penerimaan/kembalian serta indeks; jangan menganggap jalur derivasi Bitcoin berlaku.

## Pencarian transaksi dan blok

`getrawtransaction` mencari rantai aktif dan mempool, bukan transaksi yang hanya ada di cabang yatim. Input menunjuk output terdahulu, bukan satu alamat pengirim unik. `getblock` menerima `verbose` Boolean; blok tidak aktif yang tersimpan memiliki `active=false`, `confirmations=-1`. Transaksi mentahnya tetap dapat diakses melalui hash blok. `findspendingtransaction` hanya mencari pembelanjaan terkonfirmasi pada rantai aktif; null bukan bukti ketersediaan. Periksa `gettxout` dengan `include_mempool=true`. Konfirmasi dan status aktif bisa berubah setelah reorganisasi.

[API_CONTRACT.json](../../../API_CONTRACT.json)
