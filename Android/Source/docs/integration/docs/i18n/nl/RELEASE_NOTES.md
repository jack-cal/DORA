# SUMUWW Android 0.6.95 · Versieopmerkingen

SUMUWW Android 0.6.95 · De node valideert, bewaart, verspreidt en ontsluit ketengegevens.

De API-specificatie beschrijft de ingebouwde nodekern. De Android-app heeft geen RPC-instellingenscherm.

## RPC- en HTTP-API

validateaddress controleert controlesom en gekozen netwerk. decoderawtransaction geeft decoded_only, geen bewijs van een geldige handtekening of bevestiging. OP_RETURN bewaart gegevens voor externe programma’s. De node biedt kostenopvragen, controle vóór verzending, de status van RBF-vervangingen en gegevens in blokvolgorde. Vervangingen worden gecontroleerd voordat wachtende transacties worden verwijderd. Meervoudige handtekeningen en vergrendelde outputs zijn geïmplementeerd voor afzonderlijke activeringstests; ze zijn nog niet actief op het openbare netwerk.

[API_CONTRACT.json](../../../API_CONTRACT.json)
