# SUMUWW · Poznámky k vydání

SUMUWW PC 0.57.46 · Uzel ověřuje, ukládá, předává a zpřístupňuje data řetězce.

## Formát podpisu

Volitelné SDK ve zdrojích sestavuje transakce a ověřuje dodané podpisy bez klíčů a sítě. Není to podepisovací program ani příkaz uzlu. Omezení P2WPKH platí pro formát příkladu, nikoli pro uzel. Dosavadní osobní peněženka zůstává dostupná.

## RPC a HTTP API

validateaddress kontroluje kontrolní součet a zvolenou síť. decoded_only z decoderawtransaction znamená pouze rozbor, nikoli platnost podpisu či potvrzení. OP_RETURN uchovává data pro externí programy. Uzel přidává dotazy na poplatky, kontrolu před odesláním, stav náhrady RBF a čtení dat v pořadí bloků. Náhrada se ověří před odstraněním čekajících transakcí. Vícenásobné podpisy a uzamčené výstupy jsou implementovány pro oddělené testy aktivace; ve veřejné síti zatím nejsou aktivní.

## Ověření

Po instalaci závislostí spusťte ze zdrojů python examples/node_contract.py. Veřejné testovací klíče a dočasný regtest ověřují odeslání, odmítnutí, potvrzení, reorganizaci a uchování dat. Nepoužívají se skutečné prostředky, uživatelské profily ani hardwarové podepisovače.

[Dokumentace](README.html) · [Rozhraní uzlu](EXCHANGE_INTEGRATION.html) · [RPC a HTTP API](RPC_API.html) · [Provoz uzlu](NETWORK_RUNBOOK.html) · [Ověření](EXCHANGE_EXAMPLES.html)

[Podrobná anglická reference](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
