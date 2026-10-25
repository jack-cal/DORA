# SUMUWW Android 0.6.95 · Interfejs węzła

SUMUWW Android 0.6.95 · Węzeł weryfikuje, przechowuje, przekazuje i udostępnia dane łańcucha.

Specyfikacja API opisuje wbudowany rdzeń węzła. Aplikacja Android nie ma ekranu konfiguracji RPC.

## Sieć i adresy

Sieć publiczna to `sumuww`, wewnętrzny alias to `dora`. Sprawdź poniższy hash genezy. Adresy natywne używają witness v0 P2WPKH oraz HASH160 skompresowanego klucza publicznego secp256k1. Memo ani tag nie są wymagane. Odrzucaj niewłaściwą sieć i błędne sumy kontrolne. Zapisuj gałąź HD odbioru/reszty i indeks; nie zakładaj ścieżki wyprowadzania Bitcoina.

## API RPC i HTTP

validateaddress sprawdza sumę kontrolną i wybraną sieć. decoded_only z decoderawtransaction oznacza jedynie odczyt struktury, nie ważność podpisu ani potwierdzenie. OP_RETURN zachowuje dane dla programów zewnętrznych. Węzeł udostępnia zapytania o opłaty, kontrolę przed wysłaniem, stan zastąpienia RBF oraz dane w kolejności bloków. Transakcja zastępująca jest sprawdzana przed usunięciem oczekujących transakcji. Wielopodpis i blokady wyjść są zaimplementowane do izolowanych testów aktywacji; nie są jeszcze aktywne w sieci publicznej.

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

[API_CONTRACT.json](../../../API_CONTRACT.json)
