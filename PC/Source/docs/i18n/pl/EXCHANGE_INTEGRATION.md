# SUMUWW · Interfejs węzła

SUMUWW PC 0.57.46 · Węzeł weryfikuje, przechowuje, przekazuje i udostępnia dane łańcucha.

## Sieć i adresy

Sieć publiczna to `sumuww`, wewnętrzny alias to `dora`. Sprawdź poniższy hash genezy. Adresy natywne używają witness v0 P2WPKH oraz HASH160 skompresowanego klucza publicznego secp256k1. Memo ani tag nie są wymagane. Odrzucaj niewłaściwą sieć i błędne sumy kontrolne. Zapisuj gałąź HD odbioru/reszty i indeks; nie zakładaj ścieżki wyprowadzania Bitcoina.

## Format podpisu

Opcjonalny SDK w źródłach składa transakcje i weryfikuje otrzymane podpisy bez kluczy i sieci. Nie jest programem podpisującym ani poleceniem węzła. Ograniczenie P2WPKH dotyczy formatu przykładu, nie węzła. Dotychczasowy portfel osobisty pozostaje dostępny.

## API RPC i HTTP

validateaddress sprawdza sumę kontrolną i wybraną sieć. decoded_only z decoderawtransaction oznacza jedynie odczyt struktury, nie ważność podpisu ani potwierdzenie. OP_RETURN zachowuje dane dla programów zewnętrznych. Węzeł udostępnia zapytania o opłaty, kontrolę przed wysłaniem, stan zastąpienia RBF oraz dane w kolejności bloków. Transakcja zastępująca jest sprawdzana przed usunięciem oczekujących transakcji. Wielopodpis i blokady wyjść są zaimplementowane do izolowanych testów aktywacji; nie są jeszcze aktywne w sieci publicznej.

## Uwierzytelnianie i limity

Włącz RPC jawnie na numerycznym loopback `127.0.0.1:18443` z prywatnym tokenem Bearer. Brak zdalnego podpisywania i odblokowywania portfela. Użyj usługi lokalnej lub uwierzytelnionego tunelu; żądania przeglądarki Origin/Referer są odrzucane. JSON-RPC używa POST `/rpc`, obiektu/tablicy `params` oraz `id`; powiadomienia zwracają HTTP 204. Limity: treść 8004096 bajtów, nagłówki 8192, partia 16, równoległe żądania 16, czas 10 sekund; limit 1–1000, offset 0–1000000. Dostępnych jest 28 metod i 11 tras REST.

## Kwoty i dostępne wyjścia

`_units` to całkowite najmniejsze jednostki, `_smw` to tekst z 8 miejscami po przecinku, `_dora` to alias zgodności. Pole kwoty `_sumuww` nie istnieje. 1 SMW = 100000000 jednostek. `gettxout` nie ma `spendable` i może zwrócić niedojrzałą coinbase. Do wydania w następnym bloku potrzeba co najmniej 100 potwierdzeń. Filtruj `listunspent` po `spendable`; available w `getaddressbalance` wyklucza niedojrzałe środki i wejścia zajęte przez oczekujące wydatki. Nowe wyjścia mempoolu nie są potwierdzone. Sprawdzaj szczyt między stronami i ponownie waliduj wybrane wejścia.

1 SMW = 100 000 000 yugeon. Opłaty automatyczne oferują trzy poziomy na podstawie lokalnych obserwacji, bez gwarancji czasu potwierdzenia. Możesz wpisać stawkę w yugeon/vB. Przed wysłaniem sprawdź końcową opłatę i sumę w SMW. Odrzucona transakcja nie zmniejsza salda.

`1 yugeon = 0.00000001 SMW` · `1 SMW = 100000000 yugeon`

| API / wallet | yugeon / SMW |
|---|---|
| minimum relay | 1 yugeon/vB |
| automatic cap | 0.01 SMW |
| manual cap | 1 SMW |
| manual rate | 1–100000 yugeon/vB |

Opłata automatyczna uwzględnia ilość oczekujących danych, pojemność bloków i priorytet transakcji. Nie używa opłat z wcześniejszych bloków. Przy małej kolejce obowiązuje stawka minimalna. Podgląd jest odświeżany; końcowe potwierdzenie ustala opłatę. Obserwacje dotyczą połączonego lokalnego węzła, nie wszystkich węzłów.

Historia zastąpień zarejestrowanych przez ten węzeł pozostaje dostępna po ponownym uruchomieniu portfela. Usunięte transakcje nie wpływają na saldo.

Historia wydobycia pokazuje osobno nową emisję, opłaty i łączną nagrodę każdego bloku. Kwota otrzymana przez portfel jest wyświetlana oddzielnie. Przy częściowym odebraniu nagrody nie zakłada się podziału jej składników. Węzeł udostępnia 28 metod RPC, w tym szacowanie opłat, oraz weryfikuje i rozsyła podpisane transakcje.

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

[Dokumentacja](README.html) · [API RPC i HTTP](RPC_API.html) · [Obsługa węzła](NETWORK_RUNBOOK.html) · [Informacje o wersji](RELEASE_NOTES.html) · [Weryfikacja](EXCHANGE_EXAMPLES.html)

[Rozszerzona dokumentacja angielska](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
