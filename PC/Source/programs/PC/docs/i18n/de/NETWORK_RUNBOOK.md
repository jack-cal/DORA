# SUMUWW · Node-Betrieb

SUMUWW PC 0.57.46 · Der Knoten prüft, speichert, verbreitet und liefert Kettendaten.

## Netzwerk und Adressen

Das öffentliche Netzwerk heißt `sumuww`, intern auch `dora`. Prüfen Sie den unten angegebenen Genesis-Hash. Native Adressen verwenden Witness-v0-P2WPKH und HASH160 eines komprimierten secp256k1-Public-Keys. Memo oder Tag sind nicht vorgeschrieben. Falsches Netzwerk und ungültige Prüfsummen sind abzulehnen. Empfangs-/Wechselgeldzweig und HD-Index dokumentieren; nicht den Bitcoin-Ableitungspfad voraussetzen.

## Authentifizierung und Grenzen

RPC ausdrücklich auf numerischem Loopback `127.0.0.1:18443` mit privatem Bearer-Token aktivieren. Wallet-Entsperrung und Fernsignatur werden nicht angeboten. Lokalen Dienst oder authentifizierten Tunnel verwenden; Browseranfragen mit Origin/Referer werden abgelehnt. JSON-RPC verwendet POST `/rpc`, Objekt/Array `params` und `id`; Benachrichtigungen liefern HTTP 204. Grenzen: Body 8004096 Bytes, Header 8192, Batch 16, parallele Anfragen 16, Frist 10 Sekunden; limit 1–1000, offset 0–1000000. Es gibt 28 Methoden und 11 REST-Routen.

## Transaktionen und Blöcke abfragen

`getrawtransaction` durchsucht aktive Kette und Mempool, keine ausschließlich verwaisten Transaktionen. Eingänge nennen frühere Ausgänge, keine eindeutige Absenderadresse. `getblock` erwartet boolesches `verbose`; gespeicherte inaktive Blöcke haben `active=false` und `confirmations=-1`. Ihre Rohtransaktionen bleiben über den Block-Hash abrufbar. `findspendingtransaction` sucht nur bestätigte aktive Ausgaben; null beweist keine Verfügbarkeit. `gettxout` mit `include_mempool=true` prüfen. Bestätigungen und Aktivstatus können sich durch Reorganisation ändern.

## Prüfung

Installieren Sie die Abhängigkeiten und führen Sie python examples/node_contract.py im Quellcode aus. Öffentliche Testschlüssel und temporäres Regtest prüfen Übermittlung, Ablehnung, Bestätigungen, Reorganisation und Datenerhalt. Echte Guthaben, Benutzerprofile und Hardware-Signierer werden nicht verwendet.

```text
network: sumuww (dora)
genesis: 00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97
HRP: sumuww
P2P magic: d052470c
1 SMW = 100000000 yugeon
```

[Dokumentation](README.html) · [Knotenschnittstelle](EXCHANGE_INTEGRATION.html) · [RPC- und HTTP-API](RPC_API.html) · [Versionshinweise](RELEASE_NOTES.html) · [Prüfung](EXCHANGE_EXAMPLES.html)

[Ausführliche englische Referenz](../../../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../../../API_CONTRACT.json) · [vectors.json](../../../../../examples/exchange/vectors.json)
