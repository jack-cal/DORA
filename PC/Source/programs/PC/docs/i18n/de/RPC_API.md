# SUMUWW · RPC- und HTTP-API

SUMUWW PC 0.57.46 · Der Knoten prüft, speichert, verbreitet und liefert Kettendaten.

## RPC- und HTTP-API

validateaddress prüft Prüfsumme und gewähltes Netzwerk. decoderawtransaction liefert decoded_only, keine Aussage über Signaturgültigkeit oder Bestätigung. OP_RETURN-Ausgänge speichern Daten für externe Programme. Der Knoten ergänzt Gebührenabfragen, Prüfungen vor dem Senden, den RBF-Ersetzungsstatus und geordnete Blockdaten. Erst nach erfolgreicher Prüfung werden ersetzte ausstehende Transaktionen entfernt. Mehrfachsignaturen und gesperrte Ausgänge sind für isolierte Aktivierungstests implementiert und im öffentlichen Netz noch nicht aktiviert.

## Authentifizierung und Grenzen

RPC ausdrücklich auf numerischem Loopback `127.0.0.1:18443` mit privatem Bearer-Token aktivieren. Wallet-Entsperrung und Fernsignatur werden nicht angeboten. Lokalen Dienst oder authentifizierten Tunnel verwenden; Browseranfragen mit Origin/Referer werden abgelehnt. JSON-RPC verwendet POST `/rpc`, Objekt/Array `params` und `id`; Benachrichtigungen liefern HTTP 204. Grenzen: Body 8004096 Bytes, Header 8192, Batch 16, parallele Anfragen 16, Frist 10 Sekunden; limit 1–1000, offset 0–1000000. Es gibt 28 Methoden und 11 REST-Routen.

## Beträge und verfügbare Ausgänge

`_units` sind ganzzahlige kleinste Einheiten, `_smw` Zeichenketten mit 8 Nachkommastellen, `_dora` ein Kompatibilitätsalias. Ein Betragsfeld `_sumuww` existiert nicht. 1 SMW = 100000000 Einheiten. `gettxout` besitzt kein `spendable` und kann unreife Coinbase-Ausgänge liefern. Für Ausgabe im nächsten Block sind mindestens 100 Bestätigungen nötig. `listunspent` nach `spendable` filtern; available bei `getaddressbalance` schließt unreife und durch ausstehende Transaktionen belegte Mittel aus. Neue Mempool-Ausgänge sind nicht bestätigt. Spitze über mehrere Seiten prüfen und ausgewählte Eingänge revalidieren.

1 SMW = 100.000.000 yugeon. Die automatische Berechnung bietet drei Stufen anhand lokaler Beobachtungen, ohne Bestätigungszeiten zu garantieren. Sie können einen Satz in yugeon/vB eingeben. Prüfen Sie vor dem Senden die endgültige Gebühr und die Summe in SMW. Abgelehnte Transaktionen belasten das Guthaben nicht.

`1 yugeon = 0.00000001 SMW` · `1 SMW = 100000000 yugeon`

| API / wallet | yugeon / SMW |
|---|---|
| minimum relay | 1 yugeon/vB |
| automatic cap | 0.01 SMW |
| manual cap | 1 SMW |
| manual rate | 1–100000 yugeon/vB |

Automatische Gebühren berücksichtigen das ausstehende Datenvolumen, die Blockkapazität und die Transaktionspriorität. Frühere Blockgebühren werden nicht verwendet. Bei geringer Auslastung gilt der Mindestsatz. Die Vorschau wird aktualisiert; die abschließende Bestätigung legt die Gebühr fest. Die Beobachtung erfasst den verbundenen lokalen Knoten, nicht alle Knoten.

Die von diesem Knoten erfassten Ersetzungen bleiben nach dem Neustart der Wallet erhalten. Entfernte Transaktionen ändern das Guthaben nicht.

Der Mining-Verlauf zeigt neue Ausgabe, Transaktionsgebühren und Gesamtbelohnung jedes Blocks getrennt. Der von Ihrer Wallet empfangene Betrag wird separat angezeigt. Bei einer teilweise beanspruchten Belohnung wird die Aufteilung nicht angenommen. Der Knoten bietet 28 RPC-Methoden einschließlich Gebührenschätzung und prüft und verbreitet signierte Transaktionen.

## Transaktionen und Blöcke abfragen

`getrawtransaction` durchsucht aktive Kette und Mempool, keine ausschließlich verwaisten Transaktionen. Eingänge nennen frühere Ausgänge, keine eindeutige Absenderadresse. `getblock` erwartet boolesches `verbose`; gespeicherte inaktive Blöcke haben `active=false` und `confirmations=-1`. Ihre Rohtransaktionen bleiben über den Block-Hash abrufbar. `findspendingtransaction` sucht nur bestätigte aktive Ausgaben; null beweist keine Verfügbarkeit. `gettxout` mit `include_mempool=true` prüfen. Bestätigungen und Aktivstatus können sich durch Reorganisation ändern.

| method | params |
|---|---|
| `getblockchaininfo` | `{} / []` |
| `gethtlcinfo` | `{} / []` |
| `getspendinginfo` | `{} / []` |
| `getdatarecords` | `blockhash, offset=0, limit=100` |
| `decodescript` | `hex` |
| `gettxout` | `txid, index, include_mempool=true` |
| `findspendingtransaction` | `txid, index, start_height=0` |
| `getnetworkinfo` | `{} / []` |
| `getblockcount` | `{} / []` |
| `getbestblockhash` | `{} / []` |
| `getblockhash` | `height` |
| `getblock` | `hash, verbose=true` |
| `getrawmempool` | `{} / []` |
| `getmempoolinfo` | `{} / []` |
| `getmempoolpolicy` | `{} / []` |
| `estimatefee` | `vsize=140, mode=normal` |
| `testmempoolaccept` | `hex` |
| `getmempoolentry` | `txid` |
| `gettransactionstatus` | `txid` |
| `getrawtransaction` | `txid, verbose=true` |
| `decoderawtransaction` | `hex` |
| `validateaddress` | `address` |
| `listunspent` | `address, limit=100, offset=0` |
| `getaddressbalance` | `address` |
| `sendrawtransaction` | `hex` |
| `submitblock` | `hex` |
| `getblocktemplate` | `address` |
| `help` | `{} / []` |

| HTTP | URI | JSON |
|---|---|---|
| `GET` | `/api/v1/info` | `—` |
| `GET` | `/api/v1/network` | `—` |
| `GET` | `/api/v1/mempool` | `—` |
| `GET` | `/api/v1/mempool/info` | `—` |
| `GET` | `/api/v1/blocks/{height-or-hash}` | `—` |
| `GET` | `/api/v1/transactions/{txid}` | `—` |
| `GET` | `/api/v1/addresses/{address}/balance` | `—` |
| `GET` | `/api/v1/addresses/{address}/utxos?limit=100&offset=0` | `—` |
| `POST` | `/api/v1/transactions` | `{"hex":"..."}` |
| `POST` | `/api/v1/blocks` | `{"hex":"..."}` |
| `POST` | `/api/v1/mining/template` | `{"address":"..."}` |

[Dokumentation](README.html) · [Knotenschnittstelle](EXCHANGE_INTEGRATION.html) · [Node-Betrieb](NETWORK_RUNBOOK.html) · [Versionshinweise](RELEASE_NOTES.html) · [Prüfung](EXCHANGE_EXAMPLES.html)

[Ausführliche englische Referenz](../../../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../../../API_CONTRACT.json) · [vectors.json](../../../../../examples/exchange/vectors.json)
