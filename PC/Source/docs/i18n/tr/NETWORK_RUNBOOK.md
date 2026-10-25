# SUMUWW · Düğüm işletimi

SUMUWW PC 0.57.46 · Düğüm zincir verilerini doğrular, saklar, iletir ve sorgulamaya açar.

## Ağ ve adresler

Genel ağ `sumuww`, iç takma adı `dora`dır. Aşağıdaki başlangıç bloğu hashini kontrol edin. Yerel adresler witness v0 P2WPKH ve sıkıştırılmış secp256k1 açık anahtarının HASH160 değerini kullanır. Zorunlu memo veya tag yoktur. Yanlış ağ ve geçersiz sağlama toplamını reddedin. HD alma/para üstü dalını ve indeksini kaydedin; Bitcoin türetme yolunu varsaymayın.

## Kimlik doğrulama ve sınırlar

RPC’yi sayısal loopback `127.0.0.1:18443` üzerinde özel Bearer token ile açıkça etkinleştirin. Cüzdan açma veya uzaktan imza sunulmaz. Yerel hizmet ya da kimliği doğrulanmış tünel kullanın; tarayıcı Origin/Referer istekleri reddedilir. JSON-RPC; POST `/rpc`, nesne/dizi `params` ve `id` kullanır; bildirimler HTTP 204 döndürür. Sınırlar: gövde 8004096 bayt, başlıklar 8192, toplu istek 16, eşzamanlı istek 16, süre 10 saniye; limit 1–1000, offset 0–1000000. 28 yöntem ve 11 REST yolu vardır.

## İşlem ve blok sorgulama

`getrawtransaction` aktif zincir ve mempool’u arar, yalnızca ayrılmış dallardaki işlemleri aramaz. Girdiler tek bir gönderen adresini değil önceki çıktıları belirtir. `getblock`, Boolean `verbose` alır; kayıtlı pasif bloklarda `active=false`, `confirmations=-1` olur. Ham işlemler blok hashiyle erişilebilir kalır. `findspendingtransaction` yalnızca aktif zincirde onaylanmış harcamaları arar; null kullanılabilirliği kanıtlamaz. `include_mempool=true` ile `gettxout` kontrol edin. Onaylar ve aktif durum yeniden yapılanmada değişebilir.

## Doğrulama

Bağımlılıkları yükleyip kaynakta python examples/node_contract.py çalıştırın. Açık test anahtarları ve geçici regtest gönderim, ret, onay, yeniden düzenleme ve veri kalıcılığını sınar. Gerçek para, kullanıcı profili veya donanım imzalayıcı kullanılmaz.

```text
network: sumuww (dora)
genesis: 00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97
HRP: sumuww
P2P magic: d052470c
1 SMW = 100000000 yugeon
```

[Belgeler](README.html) · [Düğüm arayüzü](EXCHANGE_INTEGRATION.html) · [RPC ve HTTP API](RPC_API.html) · [Sürüm notları](RELEASE_NOTES.html) · [Doğrulama](EXCHANGE_EXAMPLES.html)

[Ayrıntılı İngilizce kaynak](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
