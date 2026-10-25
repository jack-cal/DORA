# SUMUWW · Note di versione

SUMUWW PC 0.57.46 · Il nodo verifica, conserva, inoltra e rende consultabili i dati della catena.

## Formato di firma

L’SDK opzionale nei sorgenti costruisce transazioni e verifica firme ricevute senza chiavi né rete. Non è un programma di firma o un comando del nodo. Il limite P2WPKH riguarda il formato dell’esempio, non il nodo. Il portafoglio personale esistente resta disponibile.

## API RPC e HTTP

validateaddress controlla checksum e rete scelta. decoderawtransaction restituisce decoded_only, senza attestare validità della firma o conferma. OP_RETURN conserva dati per programmi esterni. Il nodo aggiunge consultazione delle commissioni, verifica prima dell’invio, stato delle sostituzioni RBF e lettura dei dati nell’ordine dei blocchi. La sostituzione viene verificata prima di rimuovere le transazioni in attesa. Firme multiple e output bloccati sono implementati per test isolati di attivazione; non sono ancora attivi sulla rete pubblica.

## Verifica

Installate le dipendenze, eseguire python examples/node_contract.py dai sorgenti. Chiavi pubbliche di prova e regtest temporaneo verificano invio, rifiuto, conferme, riorganizzazione e persistenza. Non vengono usati fondi reali, profili personali o dispositivi di firma.

[Documentazione](README.html) · [Interfaccia del nodo](EXCHANGE_INTEGRATION.html) · [API RPC e HTTP](RPC_API.html) · [Gestione del nodo](NETWORK_RUNBOOK.html) · [Verifica](EXCHANGE_EXAMPLES.html)

[Riferimento esteso in inglese](../../../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../../../API_CONTRACT.json) · [vectors.json](../../../../../examples/exchange/vectors.json)
