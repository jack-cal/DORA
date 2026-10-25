# SUMUWW · Informacje o wersji

SUMUWW PC 0.57.46 · Węzeł weryfikuje, przechowuje, przekazuje i udostępnia dane łańcucha.

## Format podpisu

Opcjonalny SDK w źródłach składa transakcje i weryfikuje otrzymane podpisy bez kluczy i sieci. Nie jest programem podpisującym ani poleceniem węzła. Ograniczenie P2WPKH dotyczy formatu przykładu, nie węzła. Dotychczasowy portfel osobisty pozostaje dostępny.

## API RPC i HTTP

validateaddress sprawdza sumę kontrolną i wybraną sieć. decoded_only z decoderawtransaction oznacza jedynie odczyt struktury, nie ważność podpisu ani potwierdzenie. OP_RETURN zachowuje dane dla programów zewnętrznych. Węzeł udostępnia zapytania o opłaty, kontrolę przed wysłaniem, stan zastąpienia RBF oraz dane w kolejności bloków. Transakcja zastępująca jest sprawdzana przed usunięciem oczekujących transakcji. Wielopodpis i blokady wyjść są zaimplementowane do izolowanych testów aktywacji; nie są jeszcze aktywne w sieci publicznej.

## Weryfikacja

Po instalacji zależności uruchom python examples/node_contract.py ze źródeł. Jawne klucze testowe i tymczasowy regtest sprawdzają wysyłanie, odrzucanie, potwierdzenia, reorganizację i trwałość danych. Nie używamy rzeczywistych środków, profili użytkowników ani urządzeń podpisujących.

[Dokumentacja](README.html) · [Interfejs węzła](EXCHANGE_INTEGRATION.html) · [API RPC i HTTP](RPC_API.html) · [Obsługa węzła](NETWORK_RUNBOOK.html) · [Weryfikacja](EXCHANGE_EXAMPLES.html)

[Rozszerzona dokumentacja angielska](../../../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../../../API_CONTRACT.json) · [vectors.json](../../../../../examples/exchange/vectors.json)
