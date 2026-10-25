# SUMUWW · Dokumentasi

SUMUWW PC 0.57.46 · Node memvalidasi, menyimpan, meneruskan, dan menyediakan data rantai.

## Format tanda tangan

SDK sumber opsional menyusun transaksi dan memverifikasi tanda tangan yang diberikan tanpa kunci atau jaringan. Ini bukan penanda tangan atau perintah node. Batas pembayaran P2WPKH berlaku pada format contoh, bukan node. Dompet pribadi yang ada tetap tersedia.

## API RPC dan HTTP

validateaddress memeriksa checksum dan jaringan pilihan. decoded_only dari decoderawtransaction hanya berarti penguraian, bukan keabsahan tanda tangan atau konfirmasi. Output OP_RETURN menyimpan data bagi program eksternal. Node menyediakan kueri biaya, pemeriksaan sebelum pengiriman, status penggantian RBF, dan data sesuai urutan blok. Pengganti divalidasi sebelum transaksi tertunda dihapus. Multitanda tangan dan keluaran terkunci telah diterapkan untuk pengujian aktivasi terpisah; belum aktif di jaringan publik.

## Verifikasi

Pasang dependensi lalu jalankan python examples/node_contract.py dari sumber. Kunci uji publik dan regtest sementara menguji pengiriman, penolakan, konfirmasi, reorganisasi, dan persistensi. Tidak ada dana nyata, profil pengguna, atau penanda tangan perangkat keras yang digunakan.

```text
network: sumuww (dora)
genesis: 00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97
HRP: sumuww
P2P magic: d052470c
1 SMW = 100000000 yugeon
```

[Antarmuka node](EXCHANGE_INTEGRATION.html) · [API RPC dan HTTP](RPC_API.html) · [Operasi node](NETWORK_RUNBOOK.html) · [Catatan versi](RELEASE_NOTES.html) · [Verifikasi](EXCHANGE_EXAMPLES.html)

[Referensi lengkap bahasa Inggris](../../../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../../../API_CONTRACT.json) · [vectors.json](../../../../../examples/exchange/vectors.json)
