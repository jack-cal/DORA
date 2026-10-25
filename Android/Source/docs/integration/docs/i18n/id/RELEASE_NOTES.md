# SUMUWW Android 0.6.95 · Catatan versi

SUMUWW Android 0.6.95 · Node memvalidasi, menyimpan, meneruskan, dan menyediakan data rantai.

Spesifikasi API menjelaskan inti node tertanam. Aplikasi Android tidak memiliki layar pengaturan RPC.

## API RPC dan HTTP

validateaddress memeriksa checksum dan jaringan pilihan. decoded_only dari decoderawtransaction hanya berarti penguraian, bukan keabsahan tanda tangan atau konfirmasi. Output OP_RETURN menyimpan data bagi program eksternal. Node menyediakan kueri biaya, pemeriksaan sebelum pengiriman, status penggantian RBF, dan data sesuai urutan blok. Pengganti divalidasi sebelum transaksi tertunda dihapus. Multitanda tangan dan keluaran terkunci telah diterapkan untuk pengujian aktivasi terpisah; belum aktif di jaringan publik.

[API_CONTRACT.json](../../../API_CONTRACT.json)
