# SUMUWW Android 0.6.95 · Uendeshaji wa nodi

SUMUWW Android 0.6.95 · Nodi huthibitisha, huhifadhi, husambaza na kuruhusu kusoma data ya mnyororo.

## Mtandao na anwani

Mtandao wa umma ni `sumuww`, jina la ndani ni `dora`. Hakiki hash ya kitalu cha mwanzo hapa chini. Anwani hutumia witness v0 P2WPKH na HASH160 ya ufunguo wa umma wa secp256k1 uliobanwa. Memo au tag si lazima. Kataa anwani ya mtandao usio sahihi na checksum batili. Rekodi tawi la HD la kupokea/chenji na faharasa; usidhani njia ya utoaji wa funguo ya Bitcoin.

## Kutafuta miamala na vitalu

`getrawtransaction` hutafuta mnyororo hai na mempool, si miamala iliyo kwenye matawi yaliyotengwa pekee. Ingizo hutaja matokeo yaliyopita, si anwani moja ya mtumaji. `getblock` hupokea `verbose` ya Boolean; vitalu visivyo hai vilivyohifadhiwa vina `active=false`, `confirmations=-1`. Miamala ghafi bado inapatikana kwa hash ya kitalu. `findspendingtransaction` hutafuta matumizi yaliyothibitishwa katika mnyororo hai tu; null haithibitishi kupatikana. Kagua `gettxout` yenye `include_mempool=true`. Uthibitisho na hali hai vinaweza kubadilika baada ya upangaji upya.

[API_CONTRACT.json](../../../API_CONTRACT.json)
