# SUMUWW · Rozhraní uzlu

SUMUWW PC 0.57.46 · Uzel ověřuje, ukládá, předává a zpřístupňuje data řetězce.

## Síť a adresy

Veřejná síť je `sumuww`, interní alias `dora`. Ověřte níže uvedený hash genesis. Nativní adresy používají witness v0 P2WPKH a HASH160 komprimovaného veřejného klíče secp256k1. Memo ani tag nejsou povinné. Odmítněte cizí síť a chybný kontrolní součet. Zaznamenejte HD větev příjmu/vratky a index; nepředpokládejte derivační cestu Bitcoinu.

## Formát podpisu

Volitelné SDK ve zdrojích sestavuje transakce a ověřuje dodané podpisy bez klíčů a sítě. Není to podepisovací program ani příkaz uzlu. Omezení P2WPKH platí pro formát příkladu, nikoli pro uzel. Dosavadní osobní peněženka zůstává dostupná.

## RPC a HTTP API

validateaddress kontroluje kontrolní součet a zvolenou síť. decoded_only z decoderawtransaction znamená pouze rozbor, nikoli platnost podpisu či potvrzení. OP_RETURN uchovává data pro externí programy. Uzel přidává dotazy na poplatky, kontrolu před odesláním, stav náhrady RBF a čtení dat v pořadí bloků. Náhrada se ověří před odstraněním čekajících transakcí. Vícenásobné podpisy a uzamčené výstupy jsou implementovány pro oddělené testy aktivace; ve veřejné síti zatím nejsou aktivní.

## Ověření přístupu a limity

RPC zapněte výslovně na číselném loopbacku `127.0.0.1:18443` se soukromým Bearer tokenem. Odemčení peněženky ani vzdálený podpis nejsou zpřístupněny. Použijte místní službu či ověřený tunel; požadavky prohlížeče Origin/Referer se odmítají. JSON-RPC používá POST `/rpc`, objekt/pole `params` a `id`; notifikace vracejí HTTP 204. Limity: tělo 8004096 bajtů, hlavičky 8192, dávka 16, souběžné požadavky 16, lhůta 10 sekund; limit 1–1000, offset 0–1000000. K dispozici je 28 metod a 11 REST cest.

## Částky a dostupné výstupy

`_units` jsou celé nejmenší jednotky, `_smw` řetězec s 8 desetinnými místy, `_dora` kompatibilní alias. Částkové pole `_sumuww` neexistuje. 1 SMW = 100000000 jednotek. `gettxout` nemá `spendable` a může vrátit nezralé coinbase výstupy. Pro utracení v příštím bloku je nutných alespoň 100 potvrzení. Filtrujte `listunspent` přes `spendable`; available v `getaddressbalance` vynechává nezralé prostředky a čekající útraty. Nové výstupy mempoolu nejsou potvrzené. Kontrolujte vrchol mezi stránkami a znovu ověřte vybrané vstupy.

1 SMW = 100 000 000 yugeon. Automatické poplatky nabízejí tři úrovně podle místních pozorování, bez záruky času potvrzení. Sazbu v yugeon/vB lze zadat ručně. Před odesláním ověřte konečný poplatek a součet v SMW. Odmítnutá transakce nesníží zůstatek.

`1 yugeon = 0.00000001 SMW` · `1 SMW = 100000000 yugeon`

| API / wallet | yugeon / SMW |
|---|---|
| minimum relay | 1 yugeon/vB |
| automatic cap | 0.01 SMW |
| manual cap | 1 SMW |
| manual rate | 1–100000 yugeon/vB |

Automatický poplatek zohledňuje objem čekajících dat, kapacitu bloků a prioritu transakcí. Poplatky z minulých bloků nepoužívá. Při malé frontě platí minimální sazba. Náhled se aktualizuje; konečné potvrzení poplatek zafixuje. Pozorování se týká připojeného místního uzlu, nikoli všech uzlů.

Historie nahrazení zaznamenaná tímto uzlem zůstává zachována po restartu peněženky. Odstraněné transakce nemění zůstatek.

Historie těžby zobrazuje zvlášť novou emisi, poplatky a celkovou odměnu každého bloku. Částka přijatá vaší peněženkou je uvedena samostatně. Při částečném vyzvednutí se rozdělení mezi složkami nepředpokládá. Uzel poskytuje 28 metod RPC včetně odhadu poplatků a ověřuje a předává podepsané transakce.

## Vyhledání transakcí a bloků

`getrawtransaction` prohledává aktivní řetězec a mempool, nikoli výhradně osiřelé transakce. Vstupy určují předchozí výstupy, ne jednoznačného odesílatele. `getblock` používá logické `verbose`; uložené neaktivní bloky mají `active=false`, `confirmations=-1`. Surové transakce zůstávají dostupné přes hash bloku. `findspendingtransaction` hledá pouze potvrzené aktivní útraty; null nedokazuje dostupnost. Zkontrolujte `gettxout` s `include_mempool=true`. Potvrzení a aktivní stav se mohou při reorganizaci změnit.

## Ověření

Po instalaci závislostí spusťte ze zdrojů python examples/node_contract.py. Veřejné testovací klíče a dočasný regtest ověřují odeslání, odmítnutí, potvrzení, reorganizaci a uchování dat. Nepoužívají se skutečné prostředky, uživatelské profily ani hardwarové podepisovače.

```text
network: sumuww (dora)
genesis: 00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97
HRP: sumuww
P2P magic: d052470c
1 SMW = 100000000 yugeon
```

[Dokumentace](README.html) · [RPC a HTTP API](RPC_API.html) · [Provoz uzlu](NETWORK_RUNBOOK.html) · [Poznámky k vydání](RELEASE_NOTES.html) · [Ověření](EXCHANGE_EXAMPLES.html)

[Podrobná anglická reference](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
