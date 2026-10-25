# SUMUWW · RPC- och HTTP-API

SUMUWW PC 0.57.46 · Noden validerar, lagrar, vidarebefordrar och tillhandahåller kedjedata.

## RPC- och HTTP-API

validateaddress kontrollerar kontrollsumman och det valda nätverket. decoderawtransaction ger decoded_only, inget bevis på giltig signatur eller bekräftelse. OP_RETURN bevarar data för externa program. Noden lägger till avgiftsfrågor, kontroll före sändning, status för RBF-ersättning och data i blockordning. Ersättningen valideras innan väntande transaktioner tas bort. Flera signaturer och låsta utdata är implementerade för isolerade aktiveringstester; de är ännu inte aktiva i det offentliga nätverket.

## Autentisering och gränser

Aktivera RPC uttryckligen på numerisk loopback `127.0.0.1:18443` med privat Bearer-token. Ingen fjärrsignering eller upplåsning av plånbok exponeras. Använd lokal tjänst eller autentiserad tunnel; webbläsarens Origin/Referer nekas. JSON-RPC använder POST `/rpc`, objekt/array `params` och `id`; notifieringar ger HTTP 204. Gränser: kropp 8004096 byte, huvuden 8192, batch 16, samtidiga anrop 16, tidsgräns 10 sekunder; limit 1–1000, offset 0–1000000. Det finns 28 metoder och 11 REST-rutter.

## Belopp och tillgängliga utgångar

`_units` är heltal i minsta enhet; `_smw` strängar med 8 decimaler; `_dora` kompatibilitetsalias. Inget beloppsfält `_sumuww` finns. 1 SMW = 100000000 enheter. `gettxout` saknar `spendable` och kan ge omogna coinbase-utgångar. Minst 100 bekräftelser behövs för användning i nästa block. Filtrera `listunspent` på `spendable`; available i `getaddressbalance` utesluter omogna medel och väntande utgifter. Nya mempool-utgångar är inte bekräftade. Kontrollera spetsen mellan sidor och validera valda ingångar igen.

1 SMW = 100 000 000 yugeon. Automatiska avgifter erbjuder tre nivåer utifrån lokala observationer, utan att garantera bekräftelsetiden. Du kan ange en sats i yugeon/vB. Kontrollera den slutliga avgiften och totalsumman i SMW innan du skickar. En avvisad transaktion minskar inte saldot.

`1 yugeon = 0.00000001 SMW` · `1 SMW = 100000000 yugeon`

| API / wallet | yugeon / SMW |
|---|---|
| minimum relay | 1 yugeon/vB |
| automatic cap | 0.01 SMW |
| manual cap | 1 SMW |
| manual rate | 1–100000 yugeon/vB |

Automatiska avgifter utgår från väntande datamängd, blockkapacitet och transaktionsprioritet. Avgifter i tidigare block används inte. Vid kort kö gäller minimiavgiften. Förhandsvisningen uppdateras; den slutliga bekräftelsen låser avgiften. Uppgifterna gäller den anslutna lokala noden, inte alla noder.

Ersättningar som denna nod har registrerat finns kvar i historiken efter omstart av plånboken. Borttagna transaktioner påverkar inte saldot.

Utvinningshistoriken visar ny utgivning, avgifter och total belöning för varje block var för sig. Beloppet din plånbok tar emot visas separat. Vid delvis uttag antas ingen fördelning mellan delarna. Noden erbjuder 28 RPC-metoder, inklusive avgiftsuppskattning, och kontrollerar och vidarebefordrar signerade transaktioner.

## Sök transaktioner och block

`getrawtransaction` söker aktiv kedja och mempool, inte enbart övergivna transaktioner. Ingångar anger tidigare utgångar, inte en unik avsändare. `getblock` tar boolesk `verbose`; lagrade inaktiva block har `active=false`, `confirmations=-1`. Råtransaktioner kan fortsatt hämtas via blockhash. `findspendingtransaction` söker bara bekräftade aktiva utgifter; null bevisar inte tillgänglighet. Kontrollera `gettxout` med `include_mempool=true`. Bekräftelser och aktiv status kan ändras vid omorganisation.

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

[Dokumentation](README.html) · [Nodgränssnitt](EXCHANGE_INTEGRATION.html) · [Noddrift](NETWORK_RUNBOOK.html) · [Versionsinformation](RELEASE_NOTES.html) · [Verifiering](EXCHANGE_EXAMPLES.html)

[Utförlig engelsk referens](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
