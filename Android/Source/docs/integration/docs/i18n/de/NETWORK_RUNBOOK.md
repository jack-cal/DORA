# SUMUWW Android 0.6.95 · Node-Betrieb

SUMUWW Android 0.6.95 · Der Knoten prüft, speichert, verbreitet und liefert Kettendaten.

## Netzwerk und Adressen

Das öffentliche Netzwerk heißt `sumuww`, intern auch `dora`. Prüfen Sie den unten angegebenen Genesis-Hash. Native Adressen verwenden Witness-v0-P2WPKH und HASH160 eines komprimierten secp256k1-Public-Keys. Memo oder Tag sind nicht vorgeschrieben. Falsches Netzwerk und ungültige Prüfsummen sind abzulehnen. Empfangs-/Wechselgeldzweig und HD-Index dokumentieren; nicht den Bitcoin-Ableitungspfad voraussetzen.

## Transaktionen und Blöcke abfragen

`getrawtransaction` durchsucht aktive Kette und Mempool, keine ausschließlich verwaisten Transaktionen. Eingänge nennen frühere Ausgänge, keine eindeutige Absenderadresse. `getblock` erwartet boolesches `verbose`; gespeicherte inaktive Blöcke haben `active=false` und `confirmations=-1`. Ihre Rohtransaktionen bleiben über den Block-Hash abrufbar. `findspendingtransaction` sucht nur bestätigte aktive Ausgaben; null beweist keine Verfügbarkeit. `gettxout` mit `include_mempool=true` prüfen. Bestätigungen und Aktivstatus können sich durch Reorganisation ändern.

[API_CONTRACT.json](../../../API_CONTRACT.json)
