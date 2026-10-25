# SUMUWW · Nodedrift

SUMUWW PC 0.57.46 · Noden validerer, lagrer, videresender og gjør kjededata tilgjengelige.

## Nettverk og adresser

Det offentlige nettverket er `sumuww`, med internt alias `dora`. Kontroller genesis-hashen nedenfor. Native adresser bruker witness v0 P2WPKH og HASH160 av komprimert offentlig secp256k1-nøkkel. Memo eller tagg kreves ikke. Avvis feil nettverk og ugyldige kontrollsummer. Registrer HD-gren for mottak/vekslepenger og indeks; ikke anta Bitcoins avledningsbane.

## Autentisering og grenser

Aktiver RPC uttrykkelig på numerisk loopback `127.0.0.1:18443` med privat Bearer-token. Ingen fjernsignering eller opplåsing av lommebok tilbys. Bruk lokal tjeneste eller autentisert tunnel; nettleserforespørsler med Origin/Referer avvises. JSON-RPC bruker POST `/rpc`, objekt/array `params` og `id`; varslinger returnerer HTTP 204. Grenser: innhold 8004096 byte, hoder 8192, batch 16, samtidige kall 16, frist 10 sekunder; limit 1–1000, offset 0–1000000. Det finnes 28 metoder og 11 REST-ruter.

## Søk etter transaksjoner og blokker

`getrawtransaction` søker aktiv kjede og mempool, ikke transaksjoner bare i foreldreløse grener. Innganger viser tidligere utganger, ikke én avsenderadresse. `getblock` bruker boolsk `verbose`; lagrede inaktive blokker har `active=false`, `confirmations=-1`. Råtransaksjoner er fortsatt tilgjengelige via blokkhash. `findspendingtransaction` søker bare bekreftede aktive forbruk; null beviser ikke tilgjengelighet. Sjekk `gettxout` med `include_mempool=true`. Bekreftelser og aktiv status kan endres ved omorganisering.

## Verifisering

Installer avhengighetene og kjør python examples/node_contract.py fra kildekoden. Offentlige testnøkler og midlertidig regtest tester innsending, avvisning, bekreftelser, omorganisering og datalagring. Ekte midler, brukerprofiler eller maskinvare for signering brukes ikke.

```text
network: sumuww (dora)
genesis: 00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97
HRP: sumuww
P2P magic: d052470c
1 SMW = 100000000 yugeon
```

[Dokumentasjon](README.html) · [Nodegrensesnitt](EXCHANGE_INTEGRATION.html) · [RPC- og HTTP-API](RPC_API.html) · [Versjonsmerknader](RELEASE_NOTES.html) · [Verifisering](EXCHANGE_EXAMPLES.html)

[Utfyllende engelsk referanse](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
