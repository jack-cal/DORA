# SUMUWW · Noddrift

SUMUWW PC 0.57.46 · Noden validerar, lagrar, vidarebefordrar och tillhandahåller kedjedata.

## Nätverk och adresser

Det publika nätverket heter `sumuww`, internt även `dora`. Kontrollera genesis-hashen nedan. Adresser använder witness v0 P2WPKH och HASH160 av en komprimerad secp256k1-nyckel. Memo eller tagg krävs inte. Avvisa fel nätverk och ogiltiga kontrollsummor. Anteckna HD-gren för mottagning/växel och index; anta inte Bitcoins härledningsväg.

## Autentisering och gränser

Aktivera RPC uttryckligen på numerisk loopback `127.0.0.1:18443` med privat Bearer-token. Ingen fjärrsignering eller upplåsning av plånbok exponeras. Använd lokal tjänst eller autentiserad tunnel; webbläsarens Origin/Referer nekas. JSON-RPC använder POST `/rpc`, objekt/array `params` och `id`; notifieringar ger HTTP 204. Gränser: kropp 8004096 byte, huvuden 8192, batch 16, samtidiga anrop 16, tidsgräns 10 sekunder; limit 1–1000, offset 0–1000000. Det finns 28 metoder och 11 REST-rutter.

## Sök transaktioner och block

`getrawtransaction` söker aktiv kedja och mempool, inte enbart övergivna transaktioner. Ingångar anger tidigare utgångar, inte en unik avsändare. `getblock` tar boolesk `verbose`; lagrade inaktiva block har `active=false`, `confirmations=-1`. Råtransaktioner kan fortsatt hämtas via blockhash. `findspendingtransaction` söker bara bekräftade aktiva utgifter; null bevisar inte tillgänglighet. Kontrollera `gettxout` med `include_mempool=true`. Bekräftelser och aktiv status kan ändras vid omorganisation.

## Verifiering

Installera beroendena och kör python examples/node_contract.py från källkoden. Offentliga testnycklar och tillfälligt regtest prövar insändning, avvisning, bekräftelser, omorganisation och lagring. Inga riktiga medel, användarprofiler eller hårdvarusignerare används.

```text
network: sumuww (dora)
genesis: 00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97
HRP: sumuww
P2P magic: d052470c
1 SMW = 100000000 yugeon
```

[Dokumentation](README.html) · [Nodgränssnitt](EXCHANGE_INTEGRATION.html) · [RPC- och HTTP-API](RPC_API.html) · [Versionsinformation](RELEASE_NOTES.html) · [Verifiering](EXCHANGE_EXAMPLES.html)

[Utförlig engelsk referens](../../../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../../../API_CONTRACT.json) · [vectors.json](../../../../../examples/exchange/vectors.json)
