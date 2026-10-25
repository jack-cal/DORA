# SUMUWW Android 0.6.95 · Gestione del nodo

SUMUWW Android 0.6.95 · Il nodo verifica, conserva, inoltra e rende consultabili i dati della catena.

## Rete e indirizzi

La rete pubblica è `sumuww`, con alias interno `dora`. Verificare l’hash di genesi qui sotto. Gli indirizzi nativi usano P2WPKH witness v0 e HASH160 di una chiave pubblica secp256k1 compressa. Nessun memo o tag obbligatorio. Rifiutare rete errata e checksum non validi. Registrare ramo HD ricezione/resto e indice; non presumere il percorso di derivazione Bitcoin.

## Ricerca di transazioni e blocchi

`getrawtransaction` cerca nella catena attiva e nel mempool, non transazioni presenti solo in rami orfani. Gli input indicano output precedenti, non un mittente univoco. `getblock` richiede `verbose` booleano; blocchi inattivi salvati hanno `active=false` e `confirmations=-1`. Le transazioni grezze restano accessibili tramite hash del blocco. `findspendingtransaction` cerca solo spese attive confermate; null non prova disponibilità. Verificare `gettxout` con `include_mempool=true`. Conferme e stato attivo possono cambiare dopo riorganizzazione.

[API_CONTRACT.json](../../../API_CONTRACT.json)
