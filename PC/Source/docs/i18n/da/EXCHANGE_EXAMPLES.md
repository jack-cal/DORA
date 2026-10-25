# SUMUWW · Verifikation

SUMUWW PC 0.57.46 · Noden validerer, gemmer, videresender og stiller kædedata til rådighed.

## Signaturformat

Det valgfrie kildekode-SDK samler transaktioner og kontrollerer leverede signaturer uden nøgler eller netværk. Det er hverken signeringsprogram eller nodekommando. P2WPKH-begrænsningen gælder eksemplets format, ikke noden. Den personlige tegnebog er stadig tilgængelig.

## Verifikation

Installer afhængighederne og kør python examples/node_contract.py fra kildekoden. Offentlige testnøgler og midlertidigt regtest afprøver indsendelse, afvisning, bekræftelser, reorganisering og databevaring. Ingen rigtige midler, brugerprofiler eller hardware til signering bruges.

```powershell
python examples/node_contract.py
python -m unittest tests.test_node_contract tests.test_rpc -v
```

[Dokumentation](README.html) · [Nodegrænseflade](EXCHANGE_INTEGRATION.html) · [RPC- og HTTP-API](RPC_API.html) · [Nodedrift](NETWORK_RUNBOOK.html) · [Versionsnoter](RELEASE_NOTES.html)

[Uddybende engelsk reference](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
