# SUMUWW Android 0.6.95 · RPC- og HTTP-API

SUMUWW Android 0.6.95 · Noden validerer, lagrer, videresender og gjør kjededata tilgjengelige.

API-spesifikasjonen beskriver den innebygde nodekjernen. Android-appen har ingen skjerm for RPC-oppsett.

## RPC- og HTTP-API

validateaddress kontrollerer kontrollsum og valgt nettverk. decoderawtransaction gir decoded_only, ikke bevis på gyldig signatur eller bekreftelse. OP_RETURN lagrer data for eksterne programmer. Noden legger til gebyrspørringer, kontroll før sending, status for RBF-erstatning og data i blokkrekkefølge. Erstatningen valideres før ventende transaksjoner fjernes. Flere signaturer og låste utdata er implementert for isolerte aktiveringstester; de er ennå ikke aktive på det offentlige nettverket.

## Beløp og tilgjengelige utganger

`_units` er heltall i minste enhet; `_smw` tekst med 8 desimaler; `_dora` kompatibilitetsalias. Intet beløpsfelt `_sumuww` finnes. 1 SMW = 100000000 enheter. `gettxout` har ikke `spendable` og kan vise umodne coinbase-utganger. Minst 100 bekreftelser kreves for bruk i neste blokk. Filtrer `listunspent` med `spendable`; available i `getaddressbalance` utelater umodne midler og midler brukt av ventende transaksjoner. Nye mempool-utganger er ikke bekreftet. Kontroller toppen mellom sider og valider valgte innganger på nytt.

1 SMW = 100 000 000 yugeon. Automatiske gebyrer tilbyr tre nivåer basert på lokale observasjoner uten å garantere bekreftelsestiden. Du kan angi en sats i yugeon/vB. Kontroller endelig gebyr og totalsum i SMW før sending. En avvist transaksjon reduserer ikke saldoen.

`1 yugeon = 0.00000001 SMW` · `1 SMW = 100000000 yugeon`

| API / wallet | yugeon / SMW |
|---|---|
| minimum relay | 1 yugeon/vB |
| automatic cap | 0.01 SMW |
| manual cap | 1 SMW |
| manual rate | 1–100000 yugeon/vB |

Automatiske gebyrer bygger på ventende datamengde, blokkapasitet og transaksjonsprioritet. Gebyrer fra tidligere blokker brukes ikke. Ved liten kø gjelder minstesatsen. Forhåndsvisningen oppdateres; den endelige bekreftelsen låser gebyret. Opplysningene gjelder den tilkoblede lokale noden, ikke alle noder.

Erstatninger som denne noden har registrert, beholdes i historikken etter omstart av lommeboken. Fjernede transaksjoner påvirker ikke saldoen.

Utvinninghistorikken viser ny utstedelse, gebyrer og samlet belønning for hver blokk hver for seg. Beløpet lommeboken din mottar vises separat. Ved delvis uttak antas ingen fordeling mellom de to delene. Noden tilbyr 28 RPC-metoder, inkludert gebyrestimering, og kontrollerer og videresender signerte transaksjoner.

## Søk etter transaksjoner og blokker

`getrawtransaction` søker aktiv kjede og mempool, ikke transaksjoner bare i foreldreløse grener. Innganger viser tidligere utganger, ikke én avsenderadresse. `getblock` bruker boolsk `verbose`; lagrede inaktive blokker har `active=false`, `confirmations=-1`. Råtransaksjoner er fortsatt tilgjengelige via blokkhash. `findspendingtransaction` søker bare bekreftede aktive forbruk; null beviser ikke tilgjengelighet. Sjekk `gettxout` med `include_mempool=true`. Bekreftelser og aktiv status kan endres ved omorganisering.

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

[API_CONTRACT.json](../../../API_CONTRACT.json)
