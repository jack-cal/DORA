# SUMUWW · Operasi node

SUMUWW PC 0.57.46 · Node memvalidasi, menyimpan, meneruskan, dan menyediakan data rantai.

## Jaringan dan alamat

Jaringan publik adalah `sumuww`, dengan alias internal `dora`. Periksa hash genesis di bawah. Alamat asli memakai witness v0 P2WPKH dan HASH160 kunci publik secp256k1 terkompresi. Memo atau tag tidak wajib. Tolak jaringan yang salah dan checksum tidak valid. Catat cabang HD penerimaan/kembalian serta indeks; jangan menganggap jalur derivasi Bitcoin berlaku.

## Autentikasi dan batas

Aktifkan RPC secara eksplisit pada loopback numerik `127.0.0.1:18443` dengan token Bearer privat. Tidak ada pembukaan kunci dompet atau penandatanganan jarak jauh. Gunakan layanan lokal atau terowongan terautentikasi; permintaan browser Origin/Referer ditolak. JSON-RPC memakai POST `/rpc`, objek/array `params`, dan `id`; notifikasi mengembalikan HTTP 204. Batas: badan 8004096 byte, header 8192, batch 16, permintaan bersamaan 16, tenggat 10 detik; limit 1–1000, offset 0–1000000. Ada 28 metode dan 11 rute REST.

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

[Dokumentasi](README.html) · [Antarmuka node](EXCHANGE_INTEGRATION.html) · [API RPC dan HTTP](RPC_API.html) · [Catatan versi](RELEASE_NOTES.html) · [Verifikasi](EXCHANGE_EXAMPLES.html)

[Referensi lengkap bahasa Inggris](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
