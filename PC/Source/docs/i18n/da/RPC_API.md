# SUMUWW · RPC- og HTTP-API

SUMUWW PC 0.57.46 · Noden validerer, gemmer, videresender og stiller kædedata til rådighed.

## RPC- og HTTP-API

validateaddress kontrollerer kontrolsum og valgt netværk. decoderawtransaction returnerer decoded_only, ikke bevis for gyldig signatur eller bekræftelse. OP_RETURN gemmer data til eksterne programmer. Noden tilføjer gebyrforespørgsler, kontrol før afsendelse, status for RBF-erstatning og data i blokrækkefølge. Erstatningen valideres, før ventende transaktioner fjernes. Flere signaturer og låste outputs er implementeret til isolerede aktiveringstests; de er endnu ikke aktive på det offentlige netværk.

## Godkendelse og grænser

Aktivér RPC udtrykkeligt på numerisk loopback `127.0.0.1:18443` med privat Bearer-token. Der tilbydes hverken walletoplåsning eller fjernsignering. Brug lokal tjeneste eller godkendt tunnel; browserkald med Origin/Referer afvises. JSON-RPC bruger POST `/rpc`, objekt/array `params` og `id`; notifikationer giver HTTP 204. Grænser: indhold 8004096 byte, headers 8192, batch 16, samtidige kald 16, frist 10 sekunder; limit 1–1000, offset 0–1000000. Der er 28 metoder og 11 REST-ruter.

## Beløb og tilgængelige outputs

`_units` er hele mindsteenheder; `_smw` tekst med 8 decimaler; `_dora` kompatibilitetsalias. Intet beløbsfelt `_sumuww` findes. 1 SMW = 100000000 enheder. `gettxout` har ikke `spendable` og kan returnere umodne coinbase-outputs. Mindst 100 bekræftelser kræves til brug i næste blok. Filtrér `listunspent` på `spendable`; available i `getaddressbalance` udelader umodne midler og midler brugt af ventende transaktioner. Nye mempool-outputs er ikke bekræftede. Kontrollér spidsen mellem sider og validér valgte inputs igen.

1 SMW = 100.000.000 yugeon. Automatiske gebyrer tilbyder tre niveauer ud fra lokale observationer uden at garantere bekræftelsestiden. Du kan indtaste en sats i yugeon/vB. Kontrollér det endelige gebyr og totalen i SMW før afsendelse. En afvist transaktion reducerer ikke saldoen.

`1 yugeon = 0.00000001 SMW` · `1 SMW = 100000000 yugeon`

| API / wallet | yugeon / SMW |
|---|---|
| minimum relay | 1 yugeon/vB |
| automatic cap | 0.01 SMW |
| manual cap | 1 SMW |
| manual rate | 1–100000 yugeon/vB |

Automatiske gebyrer følger den ventende datamængde, blokkapaciteten og transaktionernes prioritet. Gebyrer fra tidligere blokke bruges ikke. Ved kort kø gælder minimumssatsen. Forhåndsvisningen opdateres; den endelige bekræftelse fastlægger gebyret. Oplysningerne dækker den tilsluttede lokale node, ikke alle noder.

Udskiftninger registreret af denne node bevares i historikken efter genstart af tegnebogen. Fjernede transaktioner påvirker ikke saldoen.

Minehistorikken viser ny udstedelse, gebyrer og samlet belønning for hver blok hver for sig. Det beløb, din wallet modtager, vises separat. Ved delvis udbetaling antages ingen fordeling mellem de to dele. Noden tilbyder 28 RPC-metoder, herunder gebyrestimering, og kontrollerer og videresender signerede transaktioner.

## Find transaktioner og blokke

`getrawtransaction` søger aktiv kæde og mempool, ikke transaktioner udelukkende i forældreløse grene. Inputs angiver tidligere outputs, ikke én afsenderadresse. `getblock` kræver boolesk `verbose`; gemte inaktive blokke har `active=false`, `confirmations=-1`. Råtransaktioner er stadig tilgængelige via blokhash. `findspendingtransaction` søger kun bekræftede aktive forbrug; null beviser ikke tilgængelighed. Kontrollér `gettxout` med `include_mempool=true`. Bekræftelser og aktiv status kan ændres ved reorganisering.

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

[Dokumentation](README.html) · [Nodegrænseflade](EXCHANGE_INTEGRATION.html) · [Nodedrift](NETWORK_RUNBOOK.html) · [Versionsnoter](RELEASE_NOTES.html) · [Verifikation](EXCHANGE_EXAMPLES.html)

[Uddybende engelsk reference](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
