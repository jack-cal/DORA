# SUMUWW Android 0.6.95 · Weryfikacja

SUMUWW Android 0.6.95 · Węzeł weryfikuje, przechowuje, przekazuje i udostępnia dane łańcucha.

Specyfikacja API opisuje wbudowany rdzeń węzła. Aplikacja Android nie ma ekranu konfiguracji RPC.

## API RPC i HTTP

validateaddress sprawdza sumę kontrolną i wybraną sieć. decoded_only z decoderawtransaction oznacza jedynie odczyt struktury, nie ważność podpisu ani potwierdzenie. OP_RETURN zachowuje dane dla programów zewnętrznych. Węzeł udostępnia zapytania o opłaty, kontrolę przed wysłaniem, stan zastąpienia RBF oraz dane w kolejności bloków. Transakcja zastępująca jest sprawdzana przed usunięciem oczekujących transakcji. Wielopodpis i blokady wyjść są zaimplementowane do izolowanych testów aktywacji; nie są jeszcze aktywne w sieci publicznej.

## Wyszukiwanie transakcji i bloków

`getrawtransaction` szuka w aktywnym łańcuchu i mempoolu, nie tylko w osieroconych gałęziach. Wejścia wskazują wcześniejsze wyjścia, nie jednoznaczny adres nadawcy. `getblock` przyjmuje logiczne `verbose`; zapisane nieaktywne bloki mają `active=false`, `confirmations=-1`. Surowe transakcje pozostają dostępne po hashu bloku. `findspendingtransaction` szuka tylko potwierdzonych aktywnych wydań; null nie dowodzi dostępności. Sprawdź `gettxout` z `include_mempool=true`. Potwierdzenia i aktywność mogą zmienić się po reorganizacji.

[API_CONTRACT.json](../../../API_CONTRACT.json)
