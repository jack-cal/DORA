# SUMUWW · Verificatie

SUMUWW PC 0.57.46 · De node valideert, bewaart, verspreidt en ontsluit ketengegevens.

## Ondertekenformaat

De optionele broncode-SDK stelt transacties samen en controleert aangeleverde handtekeningen zonder sleutels of netwerk. Het is geen ondertekenprogramma of nodecommando. De P2WPKH-beperking geldt voor het voorbeeldformaat, niet de node. De bestaande persoonlijke wallet blijft beschikbaar.

## Verificatie

Installeer de afhankelijkheden en voer python examples/node_contract.py uit vanuit de broncode. Openbare testsleutels en tijdelijk regtest testen indiening, afwijzing, bevestigingen, reorganisatie en gegevensbehoud. Er worden geen echte tegoeden, gebruikersprofielen of hardwareondertekenaars gebruikt.

```powershell
python examples/node_contract.py
python -m unittest tests.test_node_contract tests.test_rpc -v
```

[Documentatie](README.html) · [Node-interface](EXCHANGE_INTEGRATION.html) · [RPC- en HTTP-API](RPC_API.html) · [Nodebeheer](NETWORK_RUNBOOK.html) · [Versieopmerkingen](RELEASE_NOTES.html)

[Uitgebreide Engelse referentie](../../../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../../../API_CONTRACT.json) · [vectors.json](../../../../../examples/exchange/vectors.json)
