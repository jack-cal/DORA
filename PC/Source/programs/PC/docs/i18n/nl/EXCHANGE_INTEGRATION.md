# SUMUWW · Node-interface

SUMUWW PC 0.57.46 · De node valideert, bewaart, verspreidt en ontsluit ketengegevens.

## Netwerk en adressen

Het publieke netwerk is `sumuww`, intern ook `dora`. Controleer de genesis-hash hieronder. Native adressen gebruiken witness-v0-P2WPKH en HASH160 van een gecomprimeerde secp256k1-publieke sleutel. Memo of tag is niet verplicht. Verwerp adressen van een verkeerd netwerk en ongeldige controlesommen. Noteer HD-ontvangst-/wisselgeldtak en index; neem geen Bitcoin-afleidingspad aan.

## Ondertekenformaat

De optionele broncode-SDK stelt transacties samen en controleert aangeleverde handtekeningen zonder sleutels of netwerk. Het is geen ondertekenprogramma of nodecommando. De P2WPKH-beperking geldt voor het voorbeeldformaat, niet de node. De bestaande persoonlijke wallet blijft beschikbaar.

## RPC- en HTTP-API

validateaddress controleert controlesom en gekozen netwerk. decoderawtransaction geeft decoded_only, geen bewijs van een geldige handtekening of bevestiging. OP_RETURN bewaart gegevens voor externe programma’s. De node biedt kostenopvragen, controle vóór verzending, de status van RBF-vervangingen en gegevens in blokvolgorde. Vervangingen worden gecontroleerd voordat wachtende transacties worden verwijderd. Meervoudige handtekeningen en vergrendelde outputs zijn geïmplementeerd voor afzonderlijke activeringstests; ze zijn nog niet actief op het openbare netwerk.

## Authenticatie en limieten

Schakel RPC expliciet in op numeriek loopback `127.0.0.1:18443` met privé-Bearer-token. Walletontgrendeling en ondertekening op afstand worden niet aangeboden. Gebruik lokale service of geauthenticeerde tunnel; browserverzoeken met Origin/Referer worden geweigerd. JSON-RPC gebruikt POST `/rpc`, object/array `params` en `id`; notificaties leveren HTTP 204. Limieten: body 8004096 bytes, headers 8192, batch 16, gelijktijdige verzoeken 16, deadline 10 seconden; limit 1–1000, offset 0–1000000. Er zijn 28 methoden en 11 REST-routes.

## Bedragen en beschikbare outputs

`_units` zijn gehele kleinste eenheden; `_smw` is tekst met 8 decimalen; `_dora` een compatibiliteitsalias. Er bestaat geen bedragveld `_sumuww`. 1 SMW = 100000000 eenheden. `gettxout` heeft geen `spendable` en kan onrijpe coinbase-outputs geven. Voor besteding in het volgende blok zijn minstens 100 bevestigingen nodig. Filter `listunspent` op `spendable`; available bij `getaddressbalance` sluit onrijpe en in wachtende transacties bestede middelen uit. Nieuwe mempool-outputs zijn niet bevestigd. Controleer de ketentop tussen pagina’s en valideer gekozen inputs opnieuw.

1 SMW = 100.000.000 yugeon. Automatische kosten bieden drie niveaus op basis van lokale waarnemingen, zonder de bevestigingstijd te garanderen. U kunt een tarief in yugeon/vB invoeren. Controleer vóór verzending de definitieve kosten en het totaal in SMW. Een geweigerde transactie verlaagt het saldo niet.

`1 yugeon = 0.00000001 SMW` · `1 SMW = 100000000 yugeon`

| API / wallet | yugeon / SMW |
|---|---|
| minimum relay | 1 yugeon/vB |
| automatic cap | 0.01 SMW |
| manual cap | 1 SMW |
| manual rate | 1–100000 yugeon/vB |

Automatische kosten volgen het wachtende datavolume, de blokcapaciteit en de transactieprioriteit. Kosten uit eerdere blokken tellen niet mee. Bij weinig wachtrij blijft het minimumtarief gelden. Het voorbeeld wordt vernieuwd; de definitieve bevestiging legt de kosten vast. De waarneming geldt voor de verbonden lokale node, niet voor alle nodes.

De door dit knooppunt vastgelegde vervangingsgeschiedenis blijft na het herstarten van de wallet bewaard. Verwijderde transacties veranderen het saldo niet.

De mininggeschiedenis toont nieuwe uitgifte, transactiekosten en totale beloning per blok afzonderlijk. Het bedrag dat uw wallet ontvangt staat apart. Bij een gedeeltelijk opgeëiste beloning wordt de verdeling niet aangenomen. De node biedt 28 RPC-methoden, waaronder kostenschatting, en controleert en verspreidt ondertekende transacties.

## Transacties en blokken opzoeken

`getrawtransaction` doorzoekt actieve keten en mempool, geen uitsluitend verweesde transacties. Inputs verwijzen naar eerdere outputs, niet één afzenderadres. `getblock` gebruikt booleaanse `verbose`; opgeslagen inactieve blokken hebben `active=false`, `confirmations=-1`. Hun ruwe transacties blijven via blokhash beschikbaar. `findspendingtransaction` zoekt alleen bevestigde actieve bestedingen; null bewijst geen beschikbaarheid. Controleer `gettxout` met `include_mempool=true`. Bevestigingen en actieve status kunnen veranderen na reorganisatie.

## Verificatie

Installeer de afhankelijkheden en voer python examples/node_contract.py uit vanuit de broncode. Openbare testsleutels en tijdelijk regtest testen indiening, afwijzing, bevestigingen, reorganisatie en gegevensbehoud. Er worden geen echte tegoeden, gebruikersprofielen of hardwareondertekenaars gebruikt.

```text
network: sumuww (dora)
genesis: 00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97
HRP: sumuww
P2P magic: d052470c
1 SMW = 100000000 yugeon
```

[Documentatie](README.html) · [RPC- en HTTP-API](RPC_API.html) · [Nodebeheer](NETWORK_RUNBOOK.html) · [Versieopmerkingen](RELEASE_NOTES.html) · [Verificatie](EXCHANGE_EXAMPLES.html)

[Uitgebreide Engelse referentie](../../../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../../../API_CONTRACT.json) · [vectors.json](../../../../../examples/exchange/vectors.json)
