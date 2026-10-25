# SUMUWW Android 0.6.95 · Uhakiki

SUMUWW Android 0.6.95 · Nodi huthibitisha, huhifadhi, husambaza na kuruhusu kusoma data ya mnyororo.

Maelezo ya API yanaeleza kiini cha nodi kilichojumuishwa. Programu ya Android haina skrini ya mipangilio ya RPC.

## API ya RPC na HTTP

validateaddress hukagua checksum na mtandao uliochaguliwa. decoded_only kutoka decoderawtransaction humaanisha kusoma muundo tu, si kuthibitisha sahihi au muamala. OP_RETURN huhifadhi data kwa programu za nje. Nodi imeongezewa maswali ya ada, ukaguzi kabla ya kutuma, hali ya ubadilishaji wa RBF na rekodi za data kwa mpangilio wa vitalu. Muamala mbadala hukaguliwa kabla ya kuondoa miamala inayosubiri. Sahihi nyingi na matokeo yaliyofungwa yameundwa kwa majaribio tofauti; bado hayajawashwa kwenye mtandao wa umma.

## Kutafuta miamala na vitalu

`getrawtransaction` hutafuta mnyororo hai na mempool, si miamala iliyo kwenye matawi yaliyotengwa pekee. Ingizo hutaja matokeo yaliyopita, si anwani moja ya mtumaji. `getblock` hupokea `verbose` ya Boolean; vitalu visivyo hai vilivyohifadhiwa vina `active=false`, `confirmations=-1`. Miamala ghafi bado inapatikana kwa hash ya kitalu. `findspendingtransaction` hutafuta matumizi yaliyothibitishwa katika mnyororo hai tu; null haithibitishi kupatikana. Kagua `gettxout` yenye `include_mempool=true`. Uthibitisho na hali hai vinaweza kubadilika baada ya upangaji upya.

[API_CONTRACT.json](../../../API_CONTRACT.json)
