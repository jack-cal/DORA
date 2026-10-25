# SUMUWW · Nodegrensesnitt

SUMUWW PC 0.57.46 · Noden validerer, lagrer, videresender og gjør kjededata tilgjengelige.

## Nettverk og adresser

Det offentlige nettverket er `sumuww`, med internt alias `dora`. Kontroller genesis-hashen nedenfor. Native adresser bruker witness v0 P2WPKH og HASH160 av komprimert offentlig secp256k1-nøkkel. Memo eller tagg kreves ikke. Avvis feil nettverk og ugyldige kontrollsummer. Registrer HD-gren for mottak/vekslepenger og indeks; ikke anta Bitcoins avledningsbane.

## Signaturformat

Det valgfrie kildekode-SDK-et setter sammen transaksjoner og kontrollerer oppgitte signaturer uten nøkler eller nettverk. Det er verken signeringsprogram eller nodekommando. P2WPKH-begrensningen gjelder eksempelformatet, ikke noden. Den personlige lommeboken er fortsatt tilgjengelig.

## RPC- og HTTP-API

validateaddress kontrollerer kontrollsum og valgt nettverk. decoderawtransaction gir decoded_only, ikke bevis på gyldig signatur eller bekreftelse. OP_RETURN lagrer data for eksterne programmer. Noden legger til gebyrspørringer, kontroll før sending, status for RBF-erstatning og data i blokkrekkefølge. Erstatningen valideres før ventende transaksjoner fjernes. Flere signaturer og låste utdata er implementert for isolerte aktiveringstester; de er ennå ikke aktive på det offentlige nettverket.

## Autentisering og grenser

Aktiver RPC uttrykkelig på numerisk loopback `127.0.0.1:18443` med privat Bearer-token. Ingen fjernsignering eller opplåsing av lommebok tilbys. Bruk lokal tjeneste eller autentisert tunnel; nettleserforespørsler med Origin/Referer avvises. JSON-RPC bruker POST `/rpc`, objekt/array `params` og `id`; varslinger returnerer HTTP 204. Grenser: innhold 8004096 byte, hoder 8192, batch 16, samtidige kall 16, frist 10 sekunder; limit 1–1000, offset 0–1000000. Det finnes 28 metoder og 11 REST-ruter.

## Beløp og tilgjengelige utganger

`_units` er heltall i minste enhet; `_smw` tekst med 8 desimaler; `_dora` kompatibilitetsalias. Intet beløpsfelt `_sumuww` finnes. 1 SMW = 100000000 enheter. `gettxout` har ikke `spendable` og kan vise umodne coinbase-utganger. Minst 100 bekreftelser kreves for bruk i neste blokk. Filtrer `listunspent` med `spendable`; available i `getaddressbalance` utelater umodne midler og midler brukt av ventende transaksjoner. Nye mempool-utganger er ikke bekreftet. Kontroller toppen mellom sider og valider valgte innganger på nytt.

1 SMW = 100 000 000 yugeon. Automatiske gebyrer tilbyr tre nivåer basert på lokale observasjoner uten å garantere bekreftelsestiden. Du kan angi en sats i yugeon/vB. Kontroller endelig gebyr og totalsum i SMW før sending. En avvist transaksjon reduserer ikke saldoen.

`1 yugeon = 0.00000001 SMW` · `1 SMW = 100000000 yugeon`

| API / wallet | yugeon / SMW |
|---|---|
| minimum relay | 1 yugeon/vB |
| automatic cap | 0.01 SMW |
| manual cap | 1 SMW |
| manual rate | 1–100000 yugeon/vB |

Automatiske gebyrer bygger på ventende datamengde, blokkapasitet og transaksjonsprioritet. Gebyrer fra tidligere blokker brukes ikke. Ved liten kø gjelder minstesatsen. Forhåndsvisningen oppdateres; den endelige bekreftelsen låser gebyret. Opplysningene gjelder den tilkoblede lokale noden, ikke alle noder.

Erstatninger som denne noden har registrert, beholdes i historikken etter omstart av lommeboken. Fjernede transaksjoner påvirker ikke saldoen.

Utvinninghistorikken viser ny utstedelse, gebyrer og samlet belønning for hver blokk hver for seg. Beløpet lommeboken din mottar vises separat. Ved delvis uttak antas ingen fordeling mellom de to delene. Noden tilbyr 28 RPC-metoder, inkludert gebyrestimering, og kontrollerer og videresender signerte transaksjoner.

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

[Dokumentasjon](README.html) · [RPC- og HTTP-API](RPC_API.html) · [Nodedrift](NETWORK_RUNBOOK.html) · [Versjonsmerknader](RELEASE_NOTES.html) · [Verifisering](EXCHANGE_EXAMPLES.html)

[Utfyllende engelsk referanse](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
