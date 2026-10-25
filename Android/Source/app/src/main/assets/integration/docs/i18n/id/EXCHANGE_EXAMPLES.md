# SUMUWW Android 0.6.95 · Verifikasi

SUMUWW Android 0.6.95 · Node memvalidasi, menyimpan, meneruskan, dan menyediakan data rantai.

Spesifikasi API menjelaskan inti node tertanam. Aplikasi Android tidak memiliki layar pengaturan RPC.

## API RPC dan HTTP

validateaddress memeriksa checksum dan jaringan pilihan. decoded_only dari decoderawtransaction hanya berarti penguraian, bukan keabsahan tanda tangan atau konfirmasi. Output OP_RETURN menyimpan data bagi program eksternal. Node menyediakan kueri biaya, pemeriksaan sebelum pengiriman, status penggantian RBF, dan data sesuai urutan blok. Pengganti divalidasi sebelum transaksi tertunda dihapus. Multitanda tangan dan keluaran terkunci telah diterapkan untuk pengujian aktivasi terpisah; belum aktif di jaringan publik.

## Pencarian transaksi dan blok

`getrawtransaction` mencari rantai aktif dan mempool, bukan transaksi yang hanya ada di cabang yatim. Input menunjuk output terdahulu, bukan satu alamat pengirim unik. `getblock` menerima `verbose` Boolean; blok tidak aktif yang tersimpan memiliki `active=false`, `confirmations=-1`. Transaksi mentahnya tetap dapat diakses melalui hash blok. `findspendingtransaction` hanya mencari pembelanjaan terkonfirmasi pada rantai aktif; null bukan bukti ketersediaan. Periksa `gettxout` dengan `include_mempool=true`. Konfirmasi dan status aktif bisa berubah setelah reorganisasi.

[API_CONTRACT.json](../../../API_CONTRACT.json)
