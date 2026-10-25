# SUMUWW · Verifica

SUMUWW PC 0.57.46 · Il nodo verifica, conserva, inoltra e rende consultabili i dati della catena.

## Formato di firma

L’SDK opzionale nei sorgenti costruisce transazioni e verifica firme ricevute senza chiavi né rete. Non è un programma di firma o un comando del nodo. Il limite P2WPKH riguarda il formato dell’esempio, non il nodo. Il portafoglio personale esistente resta disponibile.

## Verifica

Installate le dipendenze, eseguire python examples/node_contract.py dai sorgenti. Chiavi pubbliche di prova e regtest temporaneo verificano invio, rifiuto, conferme, riorganizzazione e persistenza. Non vengono usati fondi reali, profili personali o dispositivi di firma.

```powershell
python examples/node_contract.py
python -m unittest tests.test_node_contract tests.test_rpc -v
```

[Documentazione](README.html) · [Interfaccia del nodo](EXCHANGE_INTEGRATION.html) · [API RPC e HTTP](RPC_API.html) · [Gestione del nodo](NETWORK_RUNBOOK.html) · [Note di versione](RELEASE_NOTES.html)

[Riferimento esteso in inglese](../../../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../../../API_CONTRACT.json) · [vectors.json](../../../../../examples/exchange/vectors.json)
