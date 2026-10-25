# SUMUWW Android 0.6.95 · API ya RPC na HTTP

SUMUWW Android 0.6.95 · Nodi huthibitisha, huhifadhi, husambaza na kuruhusu kusoma data ya mnyororo.

Maelezo ya API yanaeleza kiini cha nodi kilichojumuishwa. Programu ya Android haina skrini ya mipangilio ya RPC.

## API ya RPC na HTTP

validateaddress hukagua checksum na mtandao uliochaguliwa. decoded_only kutoka decoderawtransaction humaanisha kusoma muundo tu, si kuthibitisha sahihi au muamala. OP_RETURN huhifadhi data kwa programu za nje. Nodi imeongezewa maswali ya ada, ukaguzi kabla ya kutuma, hali ya ubadilishaji wa RBF na rekodi za data kwa mpangilio wa vitalu. Muamala mbadala hukaguliwa kabla ya kuondoa miamala inayosubiri. Sahihi nyingi na matokeo yaliyofungwa yameundwa kwa majaribio tofauti; bado hayajawashwa kwenye mtandao wa umma.

## Kiasi na matokeo yanayopatikana

`_units` ni namba kamili za kipimo kidogo zaidi; `_smw` ni maandishi yenye desimali 8; `_dora` ni jina la uoanifu. Hakuna sehemu ya kiasi `_sumuww`. 1 SMW = vipimo 100000000. `gettxout` haina `spendable` na inaweza kurudisha coinbase isiyokomaa. Angalau uthibitisho 100 unahitajika kutumia katika kitalu kinachofuata. Chuja `listunspent` kwa `spendable`; available ya `getaddressbalance` haijumuishi fedha zisizokomaa au zinazotumika na miamala inayosubiri. Matokeo mapya ya mempool hayajathibitishwa. Hakiki kilele kati ya kurasa na kagua tena ingizo zilizochaguliwa.

1 SMW = 100,000,000 yugeon. Ada ya kiotomatiki ina viwango vitatu vinavyotegemea taarifa za ndani, bila kuhakikisha muda wa uthibitisho. Unaweza kuingiza kiwango cha yugeon/vB mwenyewe. Kagua ada ya mwisho na jumla kwa SMW kabla ya kutuma. Muamala uliokataliwa haupunguzi salio.

`1 yugeon = 0.00000001 SMW` · `1 SMW = 100000000 yugeon`

| API / wallet | yugeon / SMW |
|---|---|
| minimum relay | 1 yugeon/vB |
| automatic cap | 0.01 SMW |
| manual cap | 1 SMW |
| manual rate | 1–100000 yugeon/vB |

Ada ya kiotomatiki hutegemea kiasi cha data inayosubiri, uwezo wa vitalu na kipaumbele cha miamala. Ada za vitalu vya zamani hazitumiki. Foleni ikiwa fupi, kiwango cha chini hubaki. Hakiki husasishwa; uthibitisho wa mwisho huweka ada isiyobadilika. Uchunguzi unahusu nodi ya ndani iliyounganishwa, si nodi zote.

Historia ya miamala iliyobadilishwa ambayo nodi hii imerekodi huhifadhiwa baada ya kuanzisha pochi upya. Miamala iliyoondolewa haiathiri salio.

Historia ya uchimbaji hutenganisha sarafu mpya, ada za miamala na jumla ya zawadi kwa kila bloku. Kiasi kilichopokelewa na pochi yako huonyeshwa kando. Zawadi ikidaiwa kwa sehemu, mgawanyo wa vipengele hivyo haukadiriwi. Nodi ina mbinu 28 za RPC, zikiwemo makadirio ya ada, na huthibitisha na kusambaza miamala iliyosainiwa.

## Kutafuta miamala na vitalu

`getrawtransaction` hutafuta mnyororo hai na mempool, si miamala iliyo kwenye matawi yaliyotengwa pekee. Ingizo hutaja matokeo yaliyopita, si anwani moja ya mtumaji. `getblock` hupokea `verbose` ya Boolean; vitalu visivyo hai vilivyohifadhiwa vina `active=false`, `confirmations=-1`. Miamala ghafi bado inapatikana kwa hash ya kitalu. `findspendingtransaction` hutafuta matumizi yaliyothibitishwa katika mnyororo hai tu; null haithibitishi kupatikana. Kagua `gettxout` yenye `include_mempool=true`. Uthibitisho na hali hai vinaweza kubadilika baada ya upangaji upya.

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
