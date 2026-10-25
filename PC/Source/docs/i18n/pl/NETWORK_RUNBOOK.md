# SUMUWW · Obsługa węzła

SUMUWW PC 0.57.46 · Węzeł weryfikuje, przechowuje, przekazuje i udostępnia dane łańcucha.

## Sieć i adresy

Sieć publiczna to `sumuww`, wewnętrzny alias to `dora`. Sprawdź poniższy hash genezy. Adresy natywne używają witness v0 P2WPKH oraz HASH160 skompresowanego klucza publicznego secp256k1. Memo ani tag nie są wymagane. Odrzucaj niewłaściwą sieć i błędne sumy kontrolne. Zapisuj gałąź HD odbioru/reszty i indeks; nie zakładaj ścieżki wyprowadzania Bitcoina.

## Uwierzytelnianie i limity

Włącz RPC jawnie na numerycznym loopback `127.0.0.1:18443` z prywatnym tokenem Bearer. Brak zdalnego podpisywania i odblokowywania portfela. Użyj usługi lokalnej lub uwierzytelnionego tunelu; żądania przeglądarki Origin/Referer są odrzucane. JSON-RPC używa POST `/rpc`, obiektu/tablicy `params` oraz `id`; powiadomienia zwracają HTTP 204. Limity: treść 8004096 bajtów, nagłówki 8192, partia 16, równoległe żądania 16, czas 10 sekund; limit 1–1000, offset 0–1000000. Dostępnych jest 28 metod i 11 tras REST.

## Wyszukiwanie transakcji i bloków

`getrawtransaction` szuka w aktywnym łańcuchu i mempoolu, nie tylko w osieroconych gałęziach. Wejścia wskazują wcześniejsze wyjścia, nie jednoznaczny adres nadawcy. `getblock` przyjmuje logiczne `verbose`; zapisane nieaktywne bloki mają `active=false`, `confirmations=-1`. Surowe transakcje pozostają dostępne po hashu bloku. `findspendingtransaction` szuka tylko potwierdzonych aktywnych wydań; null nie dowodzi dostępności. Sprawdź `gettxout` z `include_mempool=true`. Potwierdzenia i aktywność mogą zmienić się po reorganizacji.

## Weryfikacja

Po instalacji zależności uruchom python examples/node_contract.py ze źródeł. Jawne klucze testowe i tymczasowy regtest sprawdzają wysyłanie, odrzucanie, potwierdzenia, reorganizację i trwałość danych. Nie używamy rzeczywistych środków, profili użytkowników ani urządzeń podpisujących.

```text
network: sumuww (dora)
genesis: 00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97
HRP: sumuww
P2P magic: d052470c
1 SMW = 100000000 yugeon
```

[Dokumentacja](README.html) · [Interfejs węzła](EXCHANGE_INTEGRATION.html) · [API RPC i HTTP](RPC_API.html) · [Informacje o wersji](RELEASE_NOTES.html) · [Weryfikacja](EXCHANGE_EXAMPLES.html)

[Rozszerzona dokumentacja angielska](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
