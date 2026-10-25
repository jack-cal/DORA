# SUMUWW Android 0.6.95 · Dokumentation

SUMUWW Android 0.6.95 · Der Knoten prüft, speichert, verbreitet und liefert Kettendaten.

## Netzwerk und Adressen

Das öffentliche Netzwerk heißt `sumuww`, intern auch `dora`. Prüfen Sie den unten angegebenen Genesis-Hash. Native Adressen verwenden Witness-v0-P2WPKH und HASH160 eines komprimierten secp256k1-Public-Keys. Memo oder Tag sind nicht vorgeschrieben. Falsches Netzwerk und ungültige Prüfsummen sind abzulehnen. Empfangs-/Wechselgeldzweig und HD-Index dokumentieren; nicht den Bitcoin-Ableitungspfad voraussetzen.

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

[API_CONTRACT.json](../../../API_CONTRACT.json)
