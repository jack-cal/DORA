# SUMUWW · Nodebeheer

SUMUWW PC 0.57.46 · De node valideert, bewaart, verspreidt en ontsluit ketengegevens.

## Netwerk en adressen

Het publieke netwerk is `sumuww`, intern ook `dora`. Controleer de genesis-hash hieronder. Native adressen gebruiken witness-v0-P2WPKH en HASH160 van een gecomprimeerde secp256k1-publieke sleutel. Memo of tag is niet verplicht. Verwerp adressen van een verkeerd netwerk en ongeldige controlesommen. Noteer HD-ontvangst-/wisselgeldtak en index; neem geen Bitcoin-afleidingspad aan.

## Authenticatie en limieten

Schakel RPC expliciet in op numeriek loopback `127.0.0.1:18443` met privé-Bearer-token. Walletontgrendeling en ondertekening op afstand worden niet aangeboden. Gebruik lokale service of geauthenticeerde tunnel; browserverzoeken met Origin/Referer worden geweigerd. JSON-RPC gebruikt POST `/rpc`, object/array `params` en `id`; notificaties leveren HTTP 204. Limieten: body 8004096 bytes, headers 8192, batch 16, gelijktijdige verzoeken 16, deadline 10 seconden; limit 1–1000, offset 0–1000000. Er zijn 28 methoden en 11 REST-routes.

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

[Documentatie](README.html) · [Node-interface](EXCHANGE_INTEGRATION.html) · [RPC- en HTTP-API](RPC_API.html) · [Versieopmerkingen](RELEASE_NOTES.html) · [Verificatie](EXCHANGE_EXAMPLES.html)

[Uitgebreide Engelse referentie](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
