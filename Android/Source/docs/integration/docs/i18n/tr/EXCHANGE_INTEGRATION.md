# SUMUWW Android 0.6.95 · Düğüm arayüzü

SUMUWW Android 0.6.95 · Düğüm zincir verilerini doğrular, saklar, iletir ve sorgulamaya açar.

API belirtimi gömülü düğüm çekirdeğini açıklar. Android uygulamasında RPC yapılandırma ekranı yoktur.

## Ağ ve adresler

Genel ağ `sumuww`, iç takma adı `dora`dır. Aşağıdaki başlangıç bloğu hashini kontrol edin. Yerel adresler witness v0 P2WPKH ve sıkıştırılmış secp256k1 açık anahtarının HASH160 değerini kullanır. Zorunlu memo veya tag yoktur. Yanlış ağ ve geçersiz sağlama toplamını reddedin. HD alma/para üstü dalını ve indeksini kaydedin; Bitcoin türetme yolunu varsaymayın.

## RPC ve HTTP API

validateaddress sağlama toplamını ve seçilen ağı denetler. decoderawtransaction için decoded_only yalnızca çözümlemedir. Düğüme ücret sorgusu, gönderim öncesi kontrol, RBF değiştirme durumu ve blok sırasıyla veri okuma eklendi. Bekleyen işlemler silinmeden önce yeni işlem doğrulanır. Çoklu imza ve kilitli çıktılar, yalıtılmış etkinleştirme testleri için uygulandı; genel ağda henüz etkin değildir.

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

[API_CONTRACT.json](../../../API_CONTRACT.json)
