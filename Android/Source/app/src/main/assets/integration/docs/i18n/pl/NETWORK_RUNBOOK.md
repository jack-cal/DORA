# SUMUWW Android 0.6.95 · Obsługa węzła

SUMUWW Android 0.6.95 · Węzeł weryfikuje, przechowuje, przekazuje i udostępnia dane łańcucha.

## Sieć i adresy

Sieć publiczna to `sumuww`, wewnętrzny alias to `dora`. Sprawdź poniższy hash genezy. Adresy natywne używają witness v0 P2WPKH oraz HASH160 skompresowanego klucza publicznego secp256k1. Memo ani tag nie są wymagane. Odrzucaj niewłaściwą sieć i błędne sumy kontrolne. Zapisuj gałąź HD odbioru/reszty i indeks; nie zakładaj ścieżki wyprowadzania Bitcoina.

## Wyszukiwanie transakcji i bloków

`getrawtransaction` szuka w aktywnym łańcuchu i mempoolu, nie tylko w osieroconych gałęziach. Wejścia wskazują wcześniejsze wyjścia, nie jednoznaczny adres nadawcy. `getblock` przyjmuje logiczne `verbose`; zapisane nieaktywne bloki mają `active=false`, `confirmations=-1`. Surowe transakcje pozostają dostępne po hashu bloku. `findspendingtransaction` szuka tylko potwierdzonych aktywnych wydań; null nie dowodzi dostępności. Sprawdź `gettxout` z `include_mempool=true`. Potwierdzenia i aktywność mogą zmienić się po reorganizacji.

[API_CONTRACT.json](../../../API_CONTRACT.json)
