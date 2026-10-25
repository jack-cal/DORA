# SUMUWW · Nodedrift

SUMUWW PC 0.57.46 · Noden validerer, gemmer, videresender og stiller kædedata til rådighed.

## Netværk og adresser

Det offentlige netværk er `sumuww`, internt også `dora`. Kontrollér genesis-hashen nedenfor. Adresser bruger witness v0 P2WPKH og HASH160 af en komprimeret offentlig secp256k1-nøgle. Memo eller tag er ikke påkrævet. Afvis forkert netværk og ugyldige kontrolsummer. Notér HD-gren til modtagelse/byttepenge og indeks; antag ikke Bitcoins afledningssti.

## Godkendelse og grænser

Aktivér RPC udtrykkeligt på numerisk loopback `127.0.0.1:18443` med privat Bearer-token. Der tilbydes hverken walletoplåsning eller fjernsignering. Brug lokal tjeneste eller godkendt tunnel; browserkald med Origin/Referer afvises. JSON-RPC bruger POST `/rpc`, objekt/array `params` og `id`; notifikationer giver HTTP 204. Grænser: indhold 8004096 byte, headers 8192, batch 16, samtidige kald 16, frist 10 sekunder; limit 1–1000, offset 0–1000000. Der er 28 metoder og 11 REST-ruter.

## Find transaktioner og blokke

`getrawtransaction` søger aktiv kæde og mempool, ikke transaktioner udelukkende i forældreløse grene. Inputs angiver tidligere outputs, ikke én afsenderadresse. `getblock` kræver boolesk `verbose`; gemte inaktive blokke har `active=false`, `confirmations=-1`. Råtransaktioner er stadig tilgængelige via blokhash. `findspendingtransaction` søger kun bekræftede aktive forbrug; null beviser ikke tilgængelighed. Kontrollér `gettxout` med `include_mempool=true`. Bekræftelser og aktiv status kan ændres ved reorganisering.

## Verifikation

Installer afhængighederne og kør python examples/node_contract.py fra kildekoden. Offentlige testnøgler og midlertidigt regtest afprøver indsendelse, afvisning, bekræftelser, reorganisering og databevaring. Ingen rigtige midler, brugerprofiler eller hardware til signering bruges.

```text
network: sumuww (dora)
genesis: 00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97
HRP: sumuww
P2P magic: d052470c
1 SMW = 100000000 yugeon
```

[Dokumentation](README.html) · [Nodegrænseflade](EXCHANGE_INTEGRATION.html) · [RPC- og HTTP-API](RPC_API.html) · [Versionsnoter](RELEASE_NOTES.html) · [Verifikation](EXCHANGE_EXAMPLES.html)

[Uddybende engelsk reference](../../../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../../../API_CONTRACT.json) · [vectors.json](../../../../../examples/exchange/vectors.json)
