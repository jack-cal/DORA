# SUMUWW · Versieopmerkingen

SUMUWW PC 0.57.46 · De node valideert, bewaart, verspreidt en ontsluit ketengegevens.

## Ondertekenformaat

De optionele broncode-SDK stelt transacties samen en controleert aangeleverde handtekeningen zonder sleutels of netwerk. Het is geen ondertekenprogramma of nodecommando. De P2WPKH-beperking geldt voor het voorbeeldformaat, niet de node. De bestaande persoonlijke wallet blijft beschikbaar.

## RPC- en HTTP-API

validateaddress controleert controlesom en gekozen netwerk. decoderawtransaction geeft decoded_only, geen bewijs van een geldige handtekening of bevestiging. OP_RETURN bewaart gegevens voor externe programma’s. De node biedt kostenopvragen, controle vóór verzending, de status van RBF-vervangingen en gegevens in blokvolgorde. Vervangingen worden gecontroleerd voordat wachtende transacties worden verwijderd. Meervoudige handtekeningen en vergrendelde outputs zijn geïmplementeerd voor afzonderlijke activeringstests; ze zijn nog niet actief op het openbare netwerk.

## Verificatie

Installeer de afhankelijkheden en voer python examples/node_contract.py uit vanuit de broncode. Openbare testsleutels en tijdelijk regtest testen indiening, afwijzing, bevestigingen, reorganisatie en gegevensbehoud. Er worden geen echte tegoeden, gebruikersprofielen of hardwareondertekenaars gebruikt.

[Documentatie](README.html) · [Node-interface](EXCHANGE_INTEGRATION.html) · [RPC- en HTTP-API](RPC_API.html) · [Nodebeheer](NETWORK_RUNBOOK.html) · [Verificatie](EXCHANGE_EXAMPLES.html)

[Uitgebreide Engelse referentie](../../../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../../../API_CONTRACT.json) · [vectors.json](../../../../../examples/exchange/vectors.json)
