# SUMUWW · Weryfikacja

SUMUWW PC 0.57.46 · Węzeł weryfikuje, przechowuje, przekazuje i udostępnia dane łańcucha.

## Format podpisu

Opcjonalny SDK w źródłach składa transakcje i weryfikuje otrzymane podpisy bez kluczy i sieci. Nie jest programem podpisującym ani poleceniem węzła. Ograniczenie P2WPKH dotyczy formatu przykładu, nie węzła. Dotychczasowy portfel osobisty pozostaje dostępny.

## Weryfikacja

Po instalacji zależności uruchom python examples/node_contract.py ze źródeł. Jawne klucze testowe i tymczasowy regtest sprawdzają wysyłanie, odrzucanie, potwierdzenia, reorganizację i trwałość danych. Nie używamy rzeczywistych środków, profili użytkowników ani urządzeń podpisujących.

```powershell
python examples/node_contract.py
python -m unittest tests.test_node_contract tests.test_rpc -v
```

[Dokumentacja](README.html) · [Interfejs węzła](EXCHANGE_INTEGRATION.html) · [API RPC i HTTP](RPC_API.html) · [Obsługa węzła](NETWORK_RUNBOOK.html) · [Informacje o wersji](RELEASE_NOTES.html)

[Rozszerzona dokumentacja angielska](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
