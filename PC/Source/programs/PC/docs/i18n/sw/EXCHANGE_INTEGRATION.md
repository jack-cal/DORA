# SUMUWW · Kiolesura cha nodi

SUMUWW PC 0.57.46 · Nodi huthibitisha, huhifadhi, husambaza na kuruhusu kusoma data ya mnyororo.

## Mtandao na anwani

Mtandao wa umma ni `sumuww`, jina la ndani ni `dora`. Hakiki hash ya kitalu cha mwanzo hapa chini. Anwani hutumia witness v0 P2WPKH na HASH160 ya ufunguo wa umma wa secp256k1 uliobanwa. Memo au tag si lazima. Kataa anwani ya mtandao usio sahihi na checksum batili. Rekodi tawi la HD la kupokea/chenji na faharasa; usidhani njia ya utoaji wa funguo ya Bitcoin.

## Muundo wa saini

SDK ya hiari katika msimbo chanzo huunda miamala na kuhakiki sahihi zilizotolewa bila funguo au mtandao. Si programu ya kutia sahihi wala amri ya nodi. Kikomo cha P2WPKH ni cha muundo wa mfano, si nodi. Pochi binafsi iliyopo bado inapatikana.

## API ya RPC na HTTP

validateaddress hukagua checksum na mtandao uliochaguliwa. decoded_only kutoka decoderawtransaction humaanisha kusoma muundo tu, si kuthibitisha sahihi au muamala. OP_RETURN huhifadhi data kwa programu za nje. Nodi imeongezewa maswali ya ada, ukaguzi kabla ya kutuma, hali ya ubadilishaji wa RBF na rekodi za data kwa mpangilio wa vitalu. Muamala mbadala hukaguliwa kabla ya kuondoa miamala inayosubiri. Sahihi nyingi na matokeo yaliyofungwa yameundwa kwa majaribio tofauti; bado hayajawashwa kwenye mtandao wa umma.

## Uthibitishaji na mipaka

Washa RPC waziwazi kwenye loopback ya namba `127.0.0.1:18443` yenye tokeni binafsi ya Bearer. Hakuna kufungua pochi au kusaini kwa mbali. Tumia huduma ya ndani au handaki lenye uthibitishaji; maombi ya kivinjari ya Origin/Referer hukataliwa. JSON-RPC hutumia POST `/rpc`, kitu/safu `params` na `id`; arifa hurudisha HTTP 204. Mipaka: mwili baiti 8004096, vichwa 8192, kundi 16, maombi ya wakati mmoja 16, muda sekunde 10; limit 1–1000, offset 0–1000000. Kuna mbinu 28 na njia 11 za REST.

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

## Uhakiki

Sakinisha vitegemezi kisha endesha python examples/node_contract.py kutoka msimbo chanzo. Funguo za majaribio zilizo wazi na regtest ya muda hukagua utumaji, kukataliwa, uthibitisho, upangaji upya na uhifadhi. Hakuna fedha halisi, wasifu wa mtumiaji au kifaa cha kutia sahihi kinachotumiwa.

```text
network: sumuww (dora)
genesis: 00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97
HRP: sumuww
P2P magic: d052470c
1 SMW = 100000000 yugeon
```

[Nyaraka](README.html) · [API ya RPC na HTTP](RPC_API.html) · [Uendeshaji wa nodi](NETWORK_RUNBOOK.html) · [Maelezo ya toleo](RELEASE_NOTES.html) · [Uhakiki](EXCHANGE_EXAMPLES.html)

[Rejea ya kina ya Kiingereza](../../../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../../../API_CONTRACT.json) · [vectors.json](../../../../../examples/exchange/vectors.json)
