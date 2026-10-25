# SUMUWW · Antarmuka node

SUMUWW PC 0.57.46 · Node memvalidasi, menyimpan, meneruskan, dan menyediakan data rantai.

## Jaringan dan alamat

Jaringan publik adalah `sumuww`, dengan alias internal `dora`. Periksa hash genesis di bawah. Alamat asli memakai witness v0 P2WPKH dan HASH160 kunci publik secp256k1 terkompresi. Memo atau tag tidak wajib. Tolak jaringan yang salah dan checksum tidak valid. Catat cabang HD penerimaan/kembalian serta indeks; jangan menganggap jalur derivasi Bitcoin berlaku.

## Format tanda tangan

SDK sumber opsional menyusun transaksi dan memverifikasi tanda tangan yang diberikan tanpa kunci atau jaringan. Ini bukan penanda tangan atau perintah node. Batas pembayaran P2WPKH berlaku pada format contoh, bukan node. Dompet pribadi yang ada tetap tersedia.

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

## Verifikasi

Pasang dependensi lalu jalankan python examples/node_contract.py dari sumber. Kunci uji publik dan regtest sementara menguji pengiriman, penolakan, konfirmasi, reorganisasi, dan persistensi. Tidak ada dana nyata, profil pengguna, atau penanda tangan perangkat keras yang digunakan.

```text
network: sumuww (dora)
genesis: 00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97
HRP: sumuww
P2P magic: d052470c
1 SMW = 100000000 yugeon
```

[Dokumentasi](README.html) · [API RPC dan HTTP](RPC_API.html) · [Operasi node](NETWORK_RUNBOOK.html) · [Catatan versi](RELEASE_NOTES.html) · [Verifikasi](EXCHANGE_EXAMPLES.html)

[Referensi lengkap bahasa Inggris](../../../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../../../API_CONTRACT.json) · [vectors.json](../../../../../examples/exchange/vectors.json)
