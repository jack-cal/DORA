# SUMUWW · 0.57.44 / 0.6.93

Der Knoten ergänzt Gebührenabfragen, Prüfungen vor dem Senden, den RBF-Ersetzungsstatus und geordnete Blockdaten. Erst nach erfolgreicher Prüfung werden ersetzte ausstehende Transaktionen entfernt. Mehrfachsignaturen und gesperrte Ausgänge sind für isolierte Aktivierungstests implementiert und im öffentlichen Netz noch nicht aktiviert.

1 SMW = 100.000.000 yugeon. Die automatische Berechnung bietet drei Stufen anhand lokaler Beobachtungen, ohne Bestätigungszeiten zu garantieren. Sie können einen Satz in yugeon/vB eingeben. Prüfen Sie vor dem Senden die endgültige Gebühr und die Summe in SMW. Abgelehnte Transaktionen belasten das Guthaben nicht.

`1 yugeon = 0.00000001 SMW`

`1 SMW = 100,000,000 yugeon`

Automatische Gebühren berücksichtigen das ausstehende Datenvolumen, die Blockkapazität und die Transaktionspriorität. Frühere Blockgebühren werden nicht verwendet. Bei geringer Auslastung gilt der Mindestsatz. Die Vorschau wird aktualisiert; die abschließende Bestätigung legt die Gebühr fest. Die Beobachtung erfasst den verbundenen lokalen Knoten, nicht alle Knoten.
