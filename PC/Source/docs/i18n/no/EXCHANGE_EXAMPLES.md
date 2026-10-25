# SUMUWW · Verifisering

SUMUWW PC 0.57.46 · Noden validerer, lagrer, videresender og gjør kjededata tilgjengelige.

## Signaturformat

Det valgfrie kildekode-SDK-et setter sammen transaksjoner og kontrollerer oppgitte signaturer uten nøkler eller nettverk. Det er verken signeringsprogram eller nodekommando. P2WPKH-begrensningen gjelder eksempelformatet, ikke noden. Den personlige lommeboken er fortsatt tilgjengelig.

## Verifisering

Installer avhengighetene og kjør python examples/node_contract.py fra kildekoden. Offentlige testnøkler og midlertidig regtest tester innsending, avvisning, bekreftelser, omorganisering og datalagring. Ekte midler, brukerprofiler eller maskinvare for signering brukes ikke.

```powershell
python examples/node_contract.py
python -m unittest tests.test_node_contract tests.test_rpc -v
```

[Dokumentasjon](README.html) · [Nodegrensesnitt](EXCHANGE_INTEGRATION.html) · [RPC- og HTTP-API](RPC_API.html) · [Nodedrift](NETWORK_RUNBOOK.html) · [Versjonsmerknader](RELEASE_NOTES.html)

[Utfyllende engelsk referanse](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
