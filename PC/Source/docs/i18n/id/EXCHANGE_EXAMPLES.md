# SUMUWW · Verifikasi

SUMUWW PC 0.57.46 · Node memvalidasi, menyimpan, meneruskan, dan menyediakan data rantai.

## Format tanda tangan

SDK sumber opsional menyusun transaksi dan memverifikasi tanda tangan yang diberikan tanpa kunci atau jaringan. Ini bukan penanda tangan atau perintah node. Batas pembayaran P2WPKH berlaku pada format contoh, bukan node. Dompet pribadi yang ada tetap tersedia.

## Verifikasi

Pasang dependensi lalu jalankan python examples/node_contract.py dari sumber. Kunci uji publik dan regtest sementara menguji pengiriman, penolakan, konfirmasi, reorganisasi, dan persistensi. Tidak ada dana nyata, profil pengguna, atau penanda tangan perangkat keras yang digunakan.

```powershell
python examples/node_contract.py
python -m unittest tests.test_node_contract tests.test_rpc -v
```

[Dokumentasi](README.html) · [Antarmuka node](EXCHANGE_INTEGRATION.html) · [API RPC dan HTTP](RPC_API.html) · [Operasi node](NETWORK_RUNBOOK.html) · [Catatan versi](RELEASE_NOTES.html)

[Referensi lengkap bahasa Inggris](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
