# SUMUWW Android 0.6.95 · Nodedrift

SUMUWW Android 0.6.95 · Noden validerer, gemmer, videresender og stiller kædedata til rådighed.

## Netværk og adresser

Det offentlige netværk er `sumuww`, internt også `dora`. Kontrollér genesis-hashen nedenfor. Adresser bruger witness v0 P2WPKH og HASH160 af en komprimeret offentlig secp256k1-nøgle. Memo eller tag er ikke påkrævet. Afvis forkert netværk og ugyldige kontrolsummer. Notér HD-gren til modtagelse/byttepenge og indeks; antag ikke Bitcoins afledningssti.

## Find transaktioner og blokke

`getrawtransaction` søger aktiv kæde og mempool, ikke transaktioner udelukkende i forældreløse grene. Inputs angiver tidligere outputs, ikke én afsenderadresse. `getblock` kræver boolesk `verbose`; gemte inaktive blokke har `active=false`, `confirmations=-1`. Råtransaktioner er stadig tilgængelige via blokhash. `findspendingtransaction` søger kun bekræftede aktive forbrug; null beviser ikke tilgængelighed. Kontrollér `gettxout` med `include_mempool=true`. Bekræftelser og aktiv status kan ændres ved reorganisering.

[API_CONTRACT.json](../../../API_CONTRACT.json)
