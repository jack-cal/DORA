# SUMUWW · RPC ve HTTP API

SUMUWW PC 0.57.46 · Düğüm zincir verilerini doğrular, saklar, iletir ve sorgulamaya açar.

## RPC ve HTTP API

validateaddress sağlama toplamını ve seçilen ağı denetler. decoderawtransaction için decoded_only yalnızca çözümlemedir. Düğüme ücret sorgusu, gönderim öncesi kontrol, RBF değiştirme durumu ve blok sırasıyla veri okuma eklendi. Bekleyen işlemler silinmeden önce yeni işlem doğrulanır. Çoklu imza ve kilitli çıktılar, yalıtılmış etkinleştirme testleri için uygulandı; genel ağda henüz etkin değildir.

## Kimlik doğrulama ve sınırlar

RPC’yi sayısal loopback `127.0.0.1:18443` üzerinde özel Bearer token ile açıkça etkinleştirin. Cüzdan açma veya uzaktan imza sunulmaz. Yerel hizmet ya da kimliği doğrulanmış tünel kullanın; tarayıcı Origin/Referer istekleri reddedilir. JSON-RPC; POST `/rpc`, nesne/dizi `params` ve `id` kullanır; bildirimler HTTP 204 döndürür. Sınırlar: gövde 8004096 bayt, başlıklar 8192, toplu istek 16, eşzamanlı istek 16, süre 10 saniye; limit 1–1000, offset 0–1000000. 28 yöntem ve 11 REST yolu vardır.

## Tutarlar ve kullanılabilir çıktılar

`_units` en küçük birimin tam sayısı, `_smw` 8 ondalıklı metin, `_dora` uyumluluk takma adıdır. `_sumuww` tutar alanı yoktur. 1 SMW = 100000000 birim. `gettxout` içinde `spendable` yoktur; olgunlaşmamış coinbase çıktısı dönebilir. Sonraki blokta harcamak için en az 100 onay gerekir. `listunspent` listesini `spendable` ile süzün; `getaddressbalance` available tutarı olgunlaşmamış ve bekleyen harcamaya bağlı fonları dışlar. Yeni mempool çıktıları onaylı değildir. Sayfalar arasında zincir ucunu kontrol edin ve seçilen girdileri yeniden doğrulayın.

1 SMW = 100.000.000 yugeon. Otomatik ücret, yerel gözlemlere göre üç seçenek sunar; onay süresini garanti etmez. yugeon/vB oranını elle girebilirsiniz. Göndermeden önce son ücreti ve toplamı SMW cinsinden kontrol edin. Reddedilen işlem bakiyeyi azaltmaz.

`1 yugeon = 0.00000001 SMW` · `1 SMW = 100000000 yugeon`

| API / wallet | yugeon / SMW |
|---|---|
| minimum relay | 1 yugeon/vB |
| automatic cap | 0.01 SMW |
| manual cap | 1 SMW |
| manual rate | 1–100000 yugeon/vB |

Otomatik ücret, bekleyen veri hacmini, blok kapasitesini ve işlem önceliğini dikkate alır. Geçmiş blokların ücretleri kullanılmaz. Kuyruk kısaysa asgari oran korunur. Önizleme yenilenir; son onay ücreti sabitler. Gözlemler tüm düğümleri değil, bağlı yerel düğümü kapsar.

Bu düğümün kaydettiği işlem değiştirme geçmişi, cüzdan yeniden başlatıldığında korunur. Kaldırılan işlemler bakiyeyi etkilemez.

Madencilik geçmişi her bloğun yeni ihracını, işlem ücretlerini ve toplam ödülünü ayrı gösterir. Cüzdanınıza gelen tutar ayrıca gösterilir. Ödül kısmen talep edilmişse iki bileşenin dağılımı varsayılmaz. Düğüm, ücret tahmini dahil 28 RPC yöntemi sunar; imzalı işlemleri doğrular ve iletir.

## İşlem ve blok sorgulama

`getrawtransaction` aktif zincir ve mempool’u arar, yalnızca ayrılmış dallardaki işlemleri aramaz. Girdiler tek bir gönderen adresini değil önceki çıktıları belirtir. `getblock`, Boolean `verbose` alır; kayıtlı pasif bloklarda `active=false`, `confirmations=-1` olur. Ham işlemler blok hashiyle erişilebilir kalır. `findspendingtransaction` yalnızca aktif zincirde onaylanmış harcamaları arar; null kullanılabilirliği kanıtlamaz. `include_mempool=true` ile `gettxout` kontrol edin. Onaylar ve aktif durum yeniden yapılanmada değişebilir.

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

[Belgeler](README.html) · [Düğüm arayüzü](EXCHANGE_INTEGRATION.html) · [Düğüm işletimi](NETWORK_RUNBOOK.html) · [Sürüm notları](RELEASE_NOTES.html) · [Doğrulama](EXCHANGE_EXAMPLES.html)

[Ayrıntılı İngilizce kaynak](../../../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../../../API_CONTRACT.json) · [vectors.json](../../../../../examples/exchange/vectors.json)
