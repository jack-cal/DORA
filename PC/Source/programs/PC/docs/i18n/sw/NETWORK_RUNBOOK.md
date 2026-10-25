# SUMUWW · Uendeshaji wa nodi

SUMUWW PC 0.57.46 · Nodi huthibitisha, huhifadhi, husambaza na kuruhusu kusoma data ya mnyororo.

## Mtandao na anwani

Mtandao wa umma ni `sumuww`, jina la ndani ni `dora`. Hakiki hash ya kitalu cha mwanzo hapa chini. Anwani hutumia witness v0 P2WPKH na HASH160 ya ufunguo wa umma wa secp256k1 uliobanwa. Memo au tag si lazima. Kataa anwani ya mtandao usio sahihi na checksum batili. Rekodi tawi la HD la kupokea/chenji na faharasa; usidhani njia ya utoaji wa funguo ya Bitcoin.

## Uthibitishaji na mipaka

Washa RPC waziwazi kwenye loopback ya namba `127.0.0.1:18443` yenye tokeni binafsi ya Bearer. Hakuna kufungua pochi au kusaini kwa mbali. Tumia huduma ya ndani au handaki lenye uthibitishaji; maombi ya kivinjari ya Origin/Referer hukataliwa. JSON-RPC hutumia POST `/rpc`, kitu/safu `params` na `id`; arifa hurudisha HTTP 204. Mipaka: mwili baiti 8004096, vichwa 8192, kundi 16, maombi ya wakati mmoja 16, muda sekunde 10; limit 1–1000, offset 0–1000000. Kuna mbinu 28 na njia 11 za REST.

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

[Nyaraka](README.html) · [Kiolesura cha nodi](EXCHANGE_INTEGRATION.html) · [API ya RPC na HTTP](RPC_API.html) · [Maelezo ya toleo](RELEASE_NOTES.html) · [Uhakiki](EXCHANGE_EXAMPLES.html)

[Rejea ya kina ya Kiingereza](../../../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../../../API_CONTRACT.json) · [vectors.json](../../../../../examples/exchange/vectors.json)
