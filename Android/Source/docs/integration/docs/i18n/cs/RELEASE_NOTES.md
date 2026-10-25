# SUMUWW Android 0.6.95 · Poznámky k vydání

SUMUWW Android 0.6.95 · Uzel ověřuje, ukládá, předává a zpřístupňuje data řetězce.

Specifikace API popisuje vestavěné jádro uzlu. Aplikace Android nemá obrazovku nastavení RPC.

## RPC a HTTP API

validateaddress kontroluje kontrolní součet a zvolenou síť. decoded_only z decoderawtransaction znamená pouze rozbor, nikoli platnost podpisu či potvrzení. OP_RETURN uchovává data pro externí programy. Uzel přidává dotazy na poplatky, kontrolu před odesláním, stav náhrady RBF a čtení dat v pořadí bloků. Náhrada se ověří před odstraněním čekajících transakcí. Vícenásobné podpisy a uzamčené výstupy jsou implementovány pro oddělené testy aktivace; ve veřejné síti zatím nejsou aktivní.

[API_CONTRACT.json](../../../API_CONTRACT.json)
