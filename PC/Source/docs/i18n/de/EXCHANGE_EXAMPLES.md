# SUMUWW · Prüfung

SUMUWW PC 0.57.46 · Der Knoten prüft, speichert, verbreitet und liefert Kettendaten.

## Signaturformat

Das optionale Quellcode-SDK erstellt Transaktionen und prüft übergebene Signaturen ohne Schlüssel oder Netzwerk. Es ist weder Signierprogramm noch Knotenbefehl. Die P2WPKH-Beschränkung gilt für das Beispielformat, nicht den Knoten. Die bisherige persönliche Wallet bleibt verfügbar.

## Prüfung

Installieren Sie die Abhängigkeiten und führen Sie python examples/node_contract.py im Quellcode aus. Öffentliche Testschlüssel und temporäres Regtest prüfen Übermittlung, Ablehnung, Bestätigungen, Reorganisation und Datenerhalt. Echte Guthaben, Benutzerprofile und Hardware-Signierer werden nicht verwendet.

```powershell
python examples/node_contract.py
python -m unittest tests.test_node_contract tests.test_rpc -v
```

[Dokumentation](README.html) · [Knotenschnittstelle](EXCHANGE_INTEGRATION.html) · [RPC- und HTTP-API](RPC_API.html) · [Node-Betrieb](NETWORK_RUNBOOK.html) · [Versionshinweise](RELEASE_NOTES.html)

[Ausführliche englische Referenz](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
