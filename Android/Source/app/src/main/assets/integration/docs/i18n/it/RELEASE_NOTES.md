# SUMUWW Android 0.6.95 · Note di versione

SUMUWW Android 0.6.95 · Il nodo verifica, conserva, inoltra e rende consultabili i dati della catena.

La specifica API descrive il nucleo del nodo integrato. L’app Android non dispone di una schermata di configurazione RPC.

## API RPC e HTTP

validateaddress controlla checksum e rete scelta. decoderawtransaction restituisce decoded_only, senza attestare validità della firma o conferma. OP_RETURN conserva dati per programmi esterni. Il nodo aggiunge consultazione delle commissioni, verifica prima dell’invio, stato delle sostituzioni RBF e lettura dei dati nell’ordine dei blocchi. La sostituzione viene verificata prima di rimuovere le transazioni in attesa. Firme multiple e output bloccati sono implementati per test isolati di attivazione; non sono ancora attivi sulla rete pubblica.

[API_CONTRACT.json](../../../API_CONTRACT.json)
