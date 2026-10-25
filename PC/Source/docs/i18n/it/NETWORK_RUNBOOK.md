# SUMUWW · Gestione del nodo

SUMUWW PC 0.57.46 · Il nodo verifica, conserva, inoltra e rende consultabili i dati della catena.

## Rete e indirizzi

La rete pubblica è `sumuww`, con alias interno `dora`. Verificare l’hash di genesi qui sotto. Gli indirizzi nativi usano P2WPKH witness v0 e HASH160 di una chiave pubblica secp256k1 compressa. Nessun memo o tag obbligatorio. Rifiutare rete errata e checksum non validi. Registrare ramo HD ricezione/resto e indice; non presumere il percorso di derivazione Bitcoin.

## Autenticazione e limiti

Abilitare esplicitamente RPC sul loopback numerico `127.0.0.1:18443` con token Bearer privato. Nessuno sblocco del portafoglio o firma remota è esposto. Usare un servizio locale o tunnel autenticato; richieste browser Origin/Referer respinte. JSON-RPC usa POST `/rpc`, `params` oggetto/array e `id`; notifiche con HTTP 204. Limiti: corpo 8004096 byte, intestazioni 8192, batch 16, richieste simultanee 16, scadenza 10 secondi; limit 1–1000, offset 0–1000000. Sono disponibili 28 metodi e 11 percorsi REST.

## Ricerca di transazioni e blocchi

`getrawtransaction` cerca nella catena attiva e nel mempool, non transazioni presenti solo in rami orfani. Gli input indicano output precedenti, non un mittente univoco. `getblock` richiede `verbose` booleano; blocchi inattivi salvati hanno `active=false` e `confirmations=-1`. Le transazioni grezze restano accessibili tramite hash del blocco. `findspendingtransaction` cerca solo spese attive confermate; null non prova disponibilità. Verificare `gettxout` con `include_mempool=true`. Conferme e stato attivo possono cambiare dopo riorganizzazione.

## Verifica

Installate le dipendenze, eseguire python examples/node_contract.py dai sorgenti. Chiavi pubbliche di prova e regtest temporaneo verificano invio, rifiuto, conferme, riorganizzazione e persistenza. Non vengono usati fondi reali, profili personali o dispositivi di firma.

```text
network: sumuww (dora)
genesis: 00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97
HRP: sumuww
P2P magic: d052470c
1 SMW = 100000000 yugeon
```

[Documentazione](README.html) · [Interfaccia del nodo](EXCHANGE_INTEGRATION.html) · [API RPC e HTTP](RPC_API.html) · [Note di versione](RELEASE_NOTES.html) · [Verifica](EXCHANGE_EXAMPLES.html)

[Riferimento esteso in inglese](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
