# SUMUWW · RPC и HTTP API

SUMUWW PC 0.57.46 · Чвор проверава, чува, прослеђује и даје на увид податке ланца.

## RPC и HTTP API

validateaddress проверава контролни збир и изабрану мрежу. decoded_only из decoderawtransaction означава само читање структуре, не ваљаност потписа или потврду. OP_RETURN чува податке за спољне програме. Чвор додаје упите о накнадама, проверу пре слања, стање RBF замене и читање података редоследом блокова. Замена се проверава пре уклањања трансакција на чекању. Вишеструки потписи и закључани излази примењени су за издвојене тестове активирања; још нису активни на јавној мрежи.

## Аутентификација и ограничења

Изричито укључите RPC на нумеричком loopback-у `127.0.0.1:18443` уз приватни Bearer токен. Откључавање новчаника и удаљено потписивање нису доступни. Користите локални сервис или аутентификован тунел; Origin/Referer захтеви прегледача се одбијају. JSON-RPC користи POST `/rpc`, објекат/низ `params` и `id`; обавештења враћају HTTP 204. Границе: тело 8004096 бајтова, заглавља 8192, пакет 16, истовремени захтеви 16, рок 10 секунди; limit 1–1000, offset 0–1000000. Постоји 28 метода и 11 REST путања.

## Износи и расположиви излази

`_units` су целе најмање јединице, `_smw` текст са 8 децимала, `_dora` назив за компатибилност. Поље износа `_sumuww` не постоји. 1 SMW = 100000000 јединица. `gettxout` нема `spendable` и може вратити незреле coinbase излазе. За трошење у следећем блоку треба најмање 100 потврда. Филтрирајте `listunspent` по `spendable`; available у `getaddressbalance` искључује незрела средства и средства заузета чекајућим трошењем. Нови mempool излази нису потврђени. Проверите врх између страница и поново проверите изабране улазе.

1 SMW = 100.000.000 yugeon. Аутоматске накнаде нуде три нивоа на основу локалних запажања, без гаранције времена потврде. Стопу у yugeon/vB можете унети ручно. Пре слања проверите коначну накнаду и укупан износ у SMW. Одбијена трансакција не умањује стање.

`1 yugeon = 0.00000001 SMW` · `1 SMW = 100000000 yugeon`

| API / wallet | yugeon / SMW |
|---|---|
| minimum relay | 1 yugeon/vB |
| automatic cap | 0.01 SMW |
| manual cap | 1 SMW |
| manual rate | 1–100000 yugeon/vB |

Аутоматска накнада узима у обзир обим података на чекању, капацитет блокова и приоритет трансакција. Накнаде из ранијих блокова се не користе. Када је ред кратак, остаје минимална стопа. Преглед се освежава; коначна потврда фиксира накнаду. Подаци се односе на повезани локални чвор, а не на све чворове.

Историја замена које је забележио овај чвор остаје доступна после поновног покретања новчаника. Уклоњене трансакције не мењају стање.

Историја рударења одвојено приказује ново издавање, накнаде и укупну награду сваког блока. Износ примљен у ваш новчаник приказује се засебно. При делимичном преузимању не претпоставља се расподела између две ставке. Чвор нуди 28 RPC метода, укључујући процену накнада, и проверава и прослеђује потписане трансакције.

## Претрага трансакција и блокова

`getrawtransaction` претражује активни ланац и mempool, не трансакције само у одбаченим гранама. Улази наводе претходне излазе, не јединствену адресу пошиљаоца. `getblock` прима логички `verbose`; сачувани неактивни блокови имају `active=false`, `confirmations=-1`. Сирове трансакције остају доступне преко хеша блока. `findspendingtransaction` тражи само потврђена активна трошења; null не доказује расположивост. Проверите `gettxout` са `include_mempool=true`. Потврде и активност могу се променити реорганизацијом.

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

[Документација](README.html) · [Интерфејс чвора](EXCHANGE_INTEGRATION.html) · [Рад чвора](NETWORK_RUNBOOK.html) · [Напомене о издању](RELEASE_NOTES.html) · [Провера](EXCHANGE_EXAMPLES.html)

[Детаљан енглески приручник](../../../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../../../API_CONTRACT.json) · [vectors.json](../../../../../examples/exchange/vectors.json)
