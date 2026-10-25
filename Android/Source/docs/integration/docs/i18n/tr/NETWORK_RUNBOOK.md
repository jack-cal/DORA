# SUMUWW Android 0.6.95 · Düğüm işletimi

SUMUWW Android 0.6.95 · Düğüm zincir verilerini doğrular, saklar, iletir ve sorgulamaya açar.

## Ağ ve adresler

Genel ağ `sumuww`, iç takma adı `dora`dır. Aşağıdaki başlangıç bloğu hashini kontrol edin. Yerel adresler witness v0 P2WPKH ve sıkıştırılmış secp256k1 açık anahtarının HASH160 değerini kullanır. Zorunlu memo veya tag yoktur. Yanlış ağ ve geçersiz sağlama toplamını reddedin. HD alma/para üstü dalını ve indeksini kaydedin; Bitcoin türetme yolunu varsaymayın.

## İşlem ve blok sorgulama

`getrawtransaction` aktif zincir ve mempool’u arar, yalnızca ayrılmış dallardaki işlemleri aramaz. Girdiler tek bir gönderen adresini değil önceki çıktıları belirtir. `getblock`, Boolean `verbose` alır; kayıtlı pasif bloklarda `active=false`, `confirmations=-1` olur. Ham işlemler blok hashiyle erişilebilir kalır. `findspendingtransaction` yalnızca aktif zincirde onaylanmış harcamaları arar; null kullanılabilirliği kanıtlamaz. `include_mempool=true` ile `gettxout` kontrol edin. Onaylar ve aktif durum yeniden yapılanmada değişebilir.

[API_CONTRACT.json](../../../API_CONTRACT.json)
