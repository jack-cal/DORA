# SUMUWW Android 0.6.95 · Antarmuka node

SUMUWW Android 0.6.95 · Node memvalidasi, menyimpan, meneruskan, dan menyediakan data rantai.

Spesifikasi API menjelaskan inti node tertanam. Aplikasi Android tidak memiliki layar pengaturan RPC.

## Jaringan dan alamat

Jaringan publik adalah `sumuww`, dengan alias internal `dora`. Periksa hash genesis di bawah. Alamat asli memakai witness v0 P2WPKH dan HASH160 kunci publik secp256k1 terkompresi. Memo atau tag tidak wajib. Tolak jaringan yang salah dan checksum tidak valid. Catat cabang HD penerimaan/kembalian serta indeks; jangan menganggap jalur derivasi Bitcoin berlaku.

## API RPC dan HTTP

validateaddress memeriksa checksum dan jaringan pilihan. decoded_only dari decoderawtransaction hanya berarti penguraian, bukan keabsahan tanda tangan atau konfirmasi. Output OP_RETURN menyimpan data bagi program eksternal. Node menyediakan kueri biaya, pemeriksaan sebelum pengiriman, status penggantian RBF, dan data sesuai urutan blok. Pengganti divalidasi sebelum transaksi tertunda dihapus. Multitanda tangan dan keluaran terkunci telah diterapkan untuk pengujian aktivasi terpisah; belum aktif di jaringan publik.

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

[API_CONTRACT.json](../../../API_CONTRACT.json)
