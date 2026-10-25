# SUMUWW Android 0.6.95 · Verificatie

SUMUWW Android 0.6.95 · De node valideert, bewaart, verspreidt en ontsluit ketengegevens.

De API-specificatie beschrijft de ingebouwde nodekern. De Android-app heeft geen RPC-instellingenscherm.

## RPC- en HTTP-API

validateaddress controleert controlesom en gekozen netwerk. decoderawtransaction geeft decoded_only, geen bewijs van een geldige handtekening of bevestiging. OP_RETURN bewaart gegevens voor externe programma’s. De node biedt kostenopvragen, controle vóór verzending, de status van RBF-vervangingen en gegevens in blokvolgorde. Vervangingen worden gecontroleerd voordat wachtende transacties worden verwijderd. Meervoudige handtekeningen en vergrendelde outputs zijn geïmplementeerd voor afzonderlijke activeringstests; ze zijn nog niet actief op het openbare netwerk.

## Transacties en blokken opzoeken

`getrawtransaction` doorzoekt actieve keten en mempool, geen uitsluitend verweesde transacties. Inputs verwijzen naar eerdere outputs, niet één afzenderadres. `getblock` gebruikt booleaanse `verbose`; opgeslagen inactieve blokken hebben `active=false`, `confirmations=-1`. Hun ruwe transacties blijven via blokhash beschikbaar. `findspendingtransaction` zoekt alleen bevestigde actieve bestedingen; null bewijst geen beschikbaarheid. Controleer `gettxout` met `include_mempool=true`. Bevestigingen en actieve status kunnen veranderen na reorganisatie.

[API_CONTRACT.json](../../../API_CONTRACT.json)
