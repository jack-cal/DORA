# SUMUWW Android 0.6.95 · Documentazione

SUMUWW Android 0.6.95 · Il nodo verifica, conserva, inoltra e rende consultabili i dati della catena.

## Rete e indirizzi

La rete pubblica è `sumuww`, con alias interno `dora`. Verificare l’hash di genesi qui sotto. Gli indirizzi nativi usano P2WPKH witness v0 e HASH160 di una chiave pubblica secp256k1 compressa. Nessun memo o tag obbligatorio. Rifiutare rete errata e checksum non validi. Registrare ramo HD ricezione/resto e indice; non presumere il percorso di derivazione Bitcoin.

## Importi e output disponibili

`_units` indica unità minime intere; `_smw` stringhe a 8 decimali; `_dora` un alias compatibile. Non esiste un campo monetario `_sumuww`. 1 SMW = 100000000 unità. `gettxout` non ha `spendable` e può restituire coinbase immature. Servono almeno 100 conferme per spenderle nel blocco successivo. Filtrare `listunspent` con `spendable`; l’importo available di `getaddressbalance` esclude fondi immaturi o impegnati in spese pendenti. Nuovi output nel mempool non sono confermati. Controllare la punta tra pagine e rivalidare gli input scelti.

1 SMW = 100.000.000 yugeon. Le commissioni automatiche offrono tre livelli basati sulle osservazioni locali, senza garantire i tempi di conferma. Puoi inserire una tariffa in yugeon/vB. Prima di inviare, controlla commissione finale e totale in SMW. Una transazione rifiutata non riduce il saldo.

`1 yugeon = 0.00000001 SMW` · `1 SMW = 100000000 yugeon`

| API / wallet | yugeon / SMW |
|---|---|
| minimum relay | 1 yugeon/vB |
| automatic cap | 0.01 SMW |
| manual cap | 1 SMW |
| manual rate | 1–100000 yugeon/vB |

La commissione automatica considera il volume in attesa, la capacità dei blocchi e la priorità delle transazioni. Non usa le commissioni dei blocchi passati. Con poca attesa mantiene la tariffa minima. L’anteprima si aggiorna; la conferma finale fissa la commissione. I dati riguardano il nodo locale connesso, non tutti i nodi.

La cronologia delle sostituzioni registrate da questo nodo rimane disponibile dopo il riavvio del portafoglio. Le transazioni rimosse non modificano il saldo.

La cronologia di mining distingue nuova emissione, commissioni e ricompensa totale di ogni blocco. L’importo ricevuto dal portafoglio è mostrato separatamente. Una riscossione parziale non determina la ripartizione dei due componenti. Il nodo offre 28 metodi RPC, inclusa la stima delle commissioni, e verifica e inoltra le transazioni firmate.

## Ricerca di transazioni e blocchi

`getrawtransaction` cerca nella catena attiva e nel mempool, non transazioni presenti solo in rami orfani. Gli input indicano output precedenti, non un mittente univoco. `getblock` richiede `verbose` booleano; blocchi inattivi salvati hanno `active=false` e `confirmations=-1`. Le transazioni grezze restano accessibili tramite hash del blocco. `findspendingtransaction` cerca solo spese attive confermate; null non prova disponibilità. Verificare `gettxout` con `include_mempool=true`. Conferme e stato attivo possono cambiare dopo riorganizzazione.

[API_CONTRACT.json](../../../API_CONTRACT.json)
