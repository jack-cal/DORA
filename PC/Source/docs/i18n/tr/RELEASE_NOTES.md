# SUMUWW · Sürüm notları

SUMUWW PC 0.57.46 · Düğüm zincir verilerini doğrular, saklar, iletir ve sorgulamaya açar.

## İmza biçimi

İsteğe bağlı kaynak SDK, anahtar veya ağ olmadan işlem oluşturur ve verilen imzaları doğrular. Bir imzalama programı veya düğüm komutu değildir. P2WPKH ödeme sınırı düğüme değil örnek biçime aittir. Mevcut kişisel cüzdan kullanılabilir.

## RPC ve HTTP API

validateaddress sağlama toplamını ve seçilen ağı denetler. decoderawtransaction için decoded_only yalnızca çözümlemedir. Düğüme ücret sorgusu, gönderim öncesi kontrol, RBF değiştirme durumu ve blok sırasıyla veri okuma eklendi. Bekleyen işlemler silinmeden önce yeni işlem doğrulanır. Çoklu imza ve kilitli çıktılar, yalıtılmış etkinleştirme testleri için uygulandı; genel ağda henüz etkin değildir.

## Doğrulama

Bağımlılıkları yükleyip kaynakta python examples/node_contract.py çalıştırın. Açık test anahtarları ve geçici regtest gönderim, ret, onay, yeniden düzenleme ve veri kalıcılığını sınar. Gerçek para, kullanıcı profili veya donanım imzalayıcı kullanılmaz.

[Belgeler](README.html) · [Düğüm arayüzü](EXCHANGE_INTEGRATION.html) · [RPC ve HTTP API](RPC_API.html) · [Düğüm işletimi](NETWORK_RUNBOOK.html) · [Doğrulama](EXCHANGE_EXAMPLES.html)

[Ayrıntılı İngilizce kaynak](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
