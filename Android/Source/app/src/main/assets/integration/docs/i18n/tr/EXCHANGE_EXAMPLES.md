# SUMUWW Android 0.6.95 · Doğrulama

SUMUWW Android 0.6.95 · Düğüm zincir verilerini doğrular, saklar, iletir ve sorgulamaya açar.

API belirtimi gömülü düğüm çekirdeğini açıklar. Android uygulamasında RPC yapılandırma ekranı yoktur.

## RPC ve HTTP API

validateaddress sağlama toplamını ve seçilen ağı denetler. decoderawtransaction için decoded_only yalnızca çözümlemedir. Düğüme ücret sorgusu, gönderim öncesi kontrol, RBF değiştirme durumu ve blok sırasıyla veri okuma eklendi. Bekleyen işlemler silinmeden önce yeni işlem doğrulanır. Çoklu imza ve kilitli çıktılar, yalıtılmış etkinleştirme testleri için uygulandı; genel ağda henüz etkin değildir.

## İşlem ve blok sorgulama

`getrawtransaction` aktif zincir ve mempool’u arar, yalnızca ayrılmış dallardaki işlemleri aramaz. Girdiler tek bir gönderen adresini değil önceki çıktıları belirtir. `getblock`, Boolean `verbose` alır; kayıtlı pasif bloklarda `active=false`, `confirmations=-1` olur. Ham işlemler blok hashiyle erişilebilir kalır. `findspendingtransaction` yalnızca aktif zincirde onaylanmış harcamaları arar; null kullanılabilirliği kanıtlamaz. `include_mempool=true` ile `gettxout` kontrol edin. Onaylar ve aktif durum yeniden yapılanmada değişebilir.

[API_CONTRACT.json](../../../API_CONTRACT.json)
