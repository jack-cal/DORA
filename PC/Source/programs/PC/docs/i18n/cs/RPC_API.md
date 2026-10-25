# SUMUWW · RPC a HTTP API

SUMUWW PC 0.57.46 · Uzel ověřuje, ukládá, předává a zpřístupňuje data řetězce.

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

| method | params |
|---|---|
| `getblockchaininfo` | `{} / []` |
| `gethtlcinfo` | `{} / []` |
| `getspendinginfo` | `{} / []` |
| `getdatarecords` | `blockhash, offset=0, limit=100` |
| `decodescript` | `hex` |
| `gettxout` | `txid, index, include_mempool=true` |
| `findspendingtransaction` | `txid, index, start_height=0` |
| `getnetworkinfo` | `{} / []` |
| `getblockcount` | `{} / []` |
| `getbestblockhash` | `{} / []` |
| `getblockhash` | `height` |
| `getblock` | `hash, verbose=true` |
| `getrawmempool` | `{} / []` |
| `getmempoolinfo` | `{} / []` |
| `getmempoolpolicy` | `{} / []` |
| `estimatefee` | `vsize=140, mode=normal` |
| `testmempoolaccept` | `hex` |
| `getmempoolentry` | `txid` |
| `gettransactionstatus` | `txid` |
| `getrawtransaction` | `txid, verbose=true` |
| `decoderawtransaction` | `hex` |
| `validateaddress` | `address` |
| `listunspent` | `address, limit=100, offset=0` |
| `getaddressbalance` | `address` |
| `sendrawtransaction` | `hex` |
| `submitblock` | `hex` |
| `getblocktemplate` | `address` |
| `help` | `{} / []` |

| HTTP | URI | JSON |
|---|---|---|
| `GET` | `/api/v1/info` | `—` |
| `GET` | `/api/v1/network` | `—` |
| `GET` | `/api/v1/mempool` | `—` |
| `GET` | `/api/v1/mempool/info` | `—` |
| `GET` | `/api/v1/blocks/{height-or-hash}` | `—` |
| `GET` | `/api/v1/transactions/{txid}` | `—` |
| `GET` | `/api/v1/addresses/{address}/balance` | `—` |
| `GET` | `/api/v1/addresses/{address}/utxos?limit=100&offset=0` | `—` |
| `POST` | `/api/v1/transactions` | `{"hex":"..."}` |
| `POST` | `/api/v1/blocks` | `{"hex":"..."}` |
| `POST` | `/api/v1/mining/template` | `{"address":"..."}` |

[Dokumentace](README.html) · [Rozhraní uzlu](EXCHANGE_INTEGRATION.html) · [Provoz uzlu](NETWORK_RUNBOOK.html) · [Poznámky k vydání](RELEASE_NOTES.html) · [Ověření](EXCHANGE_EXAMPLES.html)

[Podrobná anglická reference](../../../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../../../API_CONTRACT.json) · [vectors.json](../../../../../examples/exchange/vectors.json)
