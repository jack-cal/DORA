# SUMUWW · API RPC dan HTTP

SUMUWW PC 0.57.46 · Node memvalidasi, menyimpan, meneruskan, dan menyediakan data rantai.

## API RPC dan HTTP

validateaddress memeriksa checksum dan jaringan pilihan. decoded_only dari decoderawtransaction hanya berarti penguraian, bukan keabsahan tanda tangan atau konfirmasi. Output OP_RETURN menyimpan data bagi program eksternal. Node menyediakan kueri biaya, pemeriksaan sebelum pengiriman, status penggantian RBF, dan data sesuai urutan blok. Pengganti divalidasi sebelum transaksi tertunda dihapus. Multitanda tangan dan keluaran terkunci telah diterapkan untuk pengujian aktivasi terpisah; belum aktif di jaringan publik.

## Autentikasi dan batas

Aktifkan RPC secara eksplisit pada loopback numerik `127.0.0.1:18443` dengan token Bearer privat. Tidak ada pembukaan kunci dompet atau penandatanganan jarak jauh. Gunakan layanan lokal atau terowongan terautentikasi; permintaan browser Origin/Referer ditolak. JSON-RPC memakai POST `/rpc`, objek/array `params`, dan `id`; notifikasi mengembalikan HTTP 204. Batas: badan 8004096 byte, header 8192, batch 16, permintaan bersamaan 16, tenggat 10 detik; limit 1–1000, offset 0–1000000. Ada 28 metode dan 11 rute REST.

## Jumlah dan output tersedia

`_units` adalah satuan terkecil bilangan bulat; `_smw` teks 8 desimal; `_dora` alias kompatibilitas. Tidak ada kolom jumlah `_sumuww`. 1 SMW = 100000000 satuan. `gettxout` tidak memiliki `spendable` dan dapat mengembalikan output coinbase belum matang. Perlu minimal 100 konfirmasi untuk dipakai pada blok berikutnya. Saring `listunspent` dengan `spendable`; available pada `getaddressbalance` mengecualikan dana belum matang dan yang dipakai transaksi tertunda. Output mempool baru belum terkonfirmasi. Periksa ujung rantai antarlaman dan validasi ulang input terpilih.

1 SMW = 100.000.000 yugeon. Biaya otomatis menawarkan tiga tingkat berdasarkan pengamatan lokal, tanpa menjamin waktu konfirmasi. Anda dapat memasukkan tarif yugeon/vB secara manual. Periksa biaya akhir dan total dalam SMW sebelum mengirim. Transaksi yang ditolak tidak mengurangi saldo.

`1 yugeon = 0.00000001 SMW` · `1 SMW = 100000000 yugeon`

| API / wallet | yugeon / SMW |
|---|---|
| minimum relay | 1 yugeon/vB |
| automatic cap | 0.01 SMW |
| manual cap | 1 SMW |
| manual rate | 1–100000 yugeon/vB |

Biaya otomatis mempertimbangkan volume data tertunda, kapasitas blok, dan prioritas transaksi. Biaya blok lama tidak digunakan. Saat antrean pendek, tarif minimum dipertahankan. Pratinjau diperbarui; konfirmasi akhir menetapkan biaya. Pengamatan mencakup node lokal yang terhubung, bukan semua node.

Riwayat penggantian yang dicatat node ini tetap tersimpan setelah dompet dimulai ulang. Transaksi yang dihapus tidak memengaruhi saldo.

Riwayat penambangan memisahkan penerbitan baru, biaya transaksi, dan total imbalan setiap blok. Jumlah yang diterima dompet Anda ditampilkan terpisah. Klaim sebagian tidak menentukan pembagian kedua komponen. Node menyediakan 28 metode RPC, termasuk perkiraan biaya, serta memvalidasi dan meneruskan transaksi bertanda tangan.

## Pencarian transaksi dan blok

`getrawtransaction` mencari rantai aktif dan mempool, bukan transaksi yang hanya ada di cabang yatim. Input menunjuk output terdahulu, bukan satu alamat pengirim unik. `getblock` menerima `verbose` Boolean; blok tidak aktif yang tersimpan memiliki `active=false`, `confirmations=-1`. Transaksi mentahnya tetap dapat diakses melalui hash blok. `findspendingtransaction` hanya mencari pembelanjaan terkonfirmasi pada rantai aktif; null bukan bukti ketersediaan. Periksa `gettxout` dengan `include_mempool=true`. Konfirmasi dan status aktif bisa berubah setelah reorganisasi.

| method | params |
|---|---|
| `getblockchaininfo` | `{} / []` |
| `gethtlcinfo` | `{} / []` |
| `getspendinginfo` | `{} / []` |
| `getdatarecords` | `blockhash, offset=0, limit=100` |
| `decodescript` | `hex` |
| `gettxout` | `txid, index, include_mempool=true` |
| `findspendingtransaction` | `txid, index, start_height=0` |
| `getnetworkinfo` | `{} / []` |
| `getblockcount` | `{} / []` |
| `getbestblockhash` | `{} / []` |
| `getblockhash` | `height` |
| `getblock` | `hash, verbose=true` |
| `getrawmempool` | `{} / []` |
| `getmempoolinfo` | `{} / []` |
| `getmempoolpolicy` | `{} / []` |
| `estimatefee` | `vsize=140, mode=normal` |
| `testmempoolaccept` | `hex` |
| `getmempoolentry` | `txid` |
| `gettransactionstatus` | `txid` |
| `getrawtransaction` | `txid, verbose=true` |
| `decoderawtransaction` | `hex` |
| `validateaddress` | `address` |
| `listunspent` | `address, limit=100, offset=0` |
| `getaddressbalance` | `address` |
| `sendrawtransaction` | `hex` |
| `submitblock` | `hex` |
| `getblocktemplate` | `address` |
| `help` | `{} / []` |

| HTTP | URI | JSON |
|---|---|---|
| `GET` | `/api/v1/info` | `—` |
| `GET` | `/api/v1/network` | `—` |
| `GET` | `/api/v1/mempool` | `—` |
| `GET` | `/api/v1/mempool/info` | `—` |
| `GET` | `/api/v1/blocks/{height-or-hash}` | `—` |
| `GET` | `/api/v1/transactions/{txid}` | `—` |
| `GET` | `/api/v1/addresses/{address}/balance` | `—` |
| `GET` | `/api/v1/addresses/{address}/utxos?limit=100&offset=0` | `—` |
| `POST` | `/api/v1/transactions` | `{"hex":"..."}` |
| `POST` | `/api/v1/blocks` | `{"hex":"..."}` |
| `POST` | `/api/v1/mining/template` | `{"address":"..."}` |

[Dokumentasi](README.html) · [Antarmuka node](EXCHANGE_INTEGRATION.html) · [Operasi node](NETWORK_RUNBOOK.html) · [Catatan versi](RELEASE_NOTES.html) · [Verifikasi](EXCHANGE_EXAMPLES.html)

[Referensi lengkap bahasa Inggris](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
