# SUMUWW · Dokumentation

SUMUWW PC 0.57.46 · Noden validerer, gemmer, videresender og stiller kædedata til rådighed.

## Signaturformat

Det valgfrie kildekode-SDK samler transaktioner og kontrollerer leverede signaturer uden nøgler eller netværk. Det er hverken signeringsprogram eller nodekommando. P2WPKH-begrænsningen gælder eksemplets format, ikke noden. Den personlige tegnebog er stadig tilgængelig.

## RPC- og HTTP-API

validateaddress kontrollerer kontrolsum og valgt netværk. decoderawtransaction returnerer decoded_only, ikke bevis for gyldig signatur eller bekræftelse. OP_RETURN gemmer data til eksterne programmer. Noden tilføjer gebyrforespørgsler, kontrol før afsendelse, status for RBF-erstatning og data i blokrækkefølge. Erstatningen valideres, før ventende transaktioner fjernes. Flere signaturer og låste outputs er implementeret til isolerede aktiveringstests; de er endnu ikke aktive på det offentlige netværk.

## Verifikation

Installer afhængighederne og kør python examples/node_contract.py fra kildekoden. Offentlige testnøgler og midlertidigt regtest afprøver indsendelse, afvisning, bekræftelser, reorganisering og databevaring. Ingen rigtige midler, brugerprofiler eller hardware til signering bruges.

```text
network: sumuww (dora)
genesis: 00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97
HRP: sumuww
P2P magic: d052470c
1 SMW = 100000000 yugeon
```

[Nodegrænseflade](EXCHANGE_INTEGRATION.html) · [RPC- og HTTP-API](RPC_API.html) · [Nodedrift](NETWORK_RUNBOOK.html) · [Versionsnoter](RELEASE_NOTES.html) · [Verifikation](EXCHANGE_EXAMPLES.html)

[Uddybende engelsk reference](../../../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../../../API_CONTRACT.json) · [vectors.json](../../../../../examples/exchange/vectors.json)
