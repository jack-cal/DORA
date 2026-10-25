# SUMUWW Android 0.6.95 · Ověření

SUMUWW Android 0.6.95 · Uzel ověřuje, ukládá, předává a zpřístupňuje data řetězce.

Specifikace API popisuje vestavěné jádro uzlu. Aplikace Android nemá obrazovku nastavení RPC.

## RPC a HTTP API

validateaddress kontroluje kontrolní součet a zvolenou síť. decoded_only z decoderawtransaction znamená pouze rozbor, nikoli platnost podpisu či potvrzení. OP_RETURN uchovává data pro externí programy. Uzel přidává dotazy na poplatky, kontrolu před odesláním, stav náhrady RBF a čtení dat v pořadí bloků. Náhrada se ověří před odstraněním čekajících transakcí. Vícenásobné podpisy a uzamčené výstupy jsou implementovány pro oddělené testy aktivace; ve veřejné síti zatím nejsou aktivní.

## Vyhledání transakcí a bloků

`getrawtransaction` prohledává aktivní řetězec a mempool, nikoli výhradně osiřelé transakce. Vstupy určují předchozí výstupy, ne jednoznačného odesílatele. `getblock` používá logické `verbose`; uložené neaktivní bloky mají `active=false`, `confirmations=-1`. Surové transakce zůstávají dostupné přes hash bloku. `findspendingtransaction` hledá pouze potvrzené aktivní útraty; null nedokazuje dostupnost. Zkontrolujte `gettxout` s `include_mempool=true`. Potvrzení a aktivní stav se mohou při reorganizaci změnit.

[API_CONTRACT.json](../../../API_CONTRACT.json)
