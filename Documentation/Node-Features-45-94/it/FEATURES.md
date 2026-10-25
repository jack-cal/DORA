# SUMUWW · 0.57.45 / 0.6.94

Il nodo aggiunge consultazione delle commissioni, verifica prima dell’invio, stato delle sostituzioni RBF e lettura dei dati nell’ordine dei blocchi. La sostituzione viene verificata prima di rimuovere le transazioni in attesa. Firme multiple e output bloccati sono implementati per test isolati di attivazione; non sono ancora attivi sulla rete pubblica.

1 SMW = 100.000.000 yugeon. Le commissioni automatiche offrono tre livelli basati sulle osservazioni locali, senza garantire i tempi di conferma. Puoi inserire una tariffa in yugeon/vB. Prima di inviare, controlla commissione finale e totale in SMW. Una transazione rifiutata non riduce il saldo.

`1 yugeon = 0.00000001 SMW`

`1 SMW = 100,000,000 yugeon`

La commissione automatica considera il volume in attesa, la capacità dei blocchi e la priorità delle transazioni. Non usa le commissioni dei blocchi passati. Con poca attesa mantiene la tariffa minima. L’anteprima si aggiorna; la conferma finale fissa la commissione. I dati riguardano il nodo locale connesso, non tutti i nodi.

La cronologia delle sostituzioni registrate da questo nodo rimane disponibile dopo il riavvio del portafoglio. Le transazioni rimosse non modificano il saldo.

L’esploratore mostra le condizioni rivelate di firma multipla e blocco degli output. L’attivazione sulla rete pubblica non è ancora programmata.
