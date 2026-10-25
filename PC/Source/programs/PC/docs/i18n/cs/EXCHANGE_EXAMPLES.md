# SUMUWW · Ověření

SUMUWW PC 0.57.46 · Uzel ověřuje, ukládá, předává a zpřístupňuje data řetězce.

## Formát podpisu

Volitelné SDK ve zdrojích sestavuje transakce a ověřuje dodané podpisy bez klíčů a sítě. Není to podepisovací program ani příkaz uzlu. Omezení P2WPKH platí pro formát příkladu, nikoli pro uzel. Dosavadní osobní peněženka zůstává dostupná.

## Ověření

Po instalaci závislostí spusťte ze zdrojů python examples/node_contract.py. Veřejné testovací klíče a dočasný regtest ověřují odeslání, odmítnutí, potvrzení, reorganizaci a uchování dat. Nepoužívají se skutečné prostředky, uživatelské profily ani hardwarové podepisovače.

```powershell
python examples/node_contract.py
python -m unittest tests.test_node_contract tests.test_rpc -v
```

[Dokumentace](README.html) · [Rozhraní uzlu](EXCHANGE_INTEGRATION.html) · [RPC a HTTP API](RPC_API.html) · [Provoz uzlu](NETWORK_RUNBOOK.html) · [Poznámky k vydání](RELEASE_NOTES.html)

[Podrobná anglická reference](../../../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../../../API_CONTRACT.json) · [vectors.json](../../../../../examples/exchange/vectors.json)
