# SUMUWW · Verifiering

SUMUWW PC 0.57.46 · Noden validerar, lagrar, vidarebefordrar och tillhandahåller kedjedata.

## Signeringsformat

Det valfria källkods-SDK:t sammanställer transaktioner och verifierar tillhandahållna signaturer utan nycklar eller nätverk. Det är inget signeringsprogram eller nodkommando. P2WPKH-begränsningen gäller exempelformatet, inte noden. Den personliga plånboken finns kvar.

## Verifiering

Installera beroendena och kör python examples/node_contract.py från källkoden. Offentliga testnycklar och tillfälligt regtest prövar insändning, avvisning, bekräftelser, omorganisation och lagring. Inga riktiga medel, användarprofiler eller hårdvarusignerare används.

```powershell
python examples/node_contract.py
python -m unittest tests.test_node_contract tests.test_rpc -v
```

[Dokumentation](README.html) · [Nodgränssnitt](EXCHANGE_INTEGRATION.html) · [RPC- och HTTP-API](RPC_API.html) · [Noddrift](NETWORK_RUNBOOK.html) · [Versionsinformation](RELEASE_NOTES.html)

[Utförlig engelsk referens](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
