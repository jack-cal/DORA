# SUMUWW Android 0.6.95 · Versionsnoter

SUMUWW Android 0.6.95 · Noden validerer, gemmer, videresender og stiller kædedata til rådighed.

API-specifikationen beskriver den indbyggede nodekerne. Android-appen har ingen skærm til RPC-konfiguration.

## RPC- og HTTP-API

validateaddress kontrollerer kontrolsum og valgt netværk. decoderawtransaction returnerer decoded_only, ikke bevis for gyldig signatur eller bekræftelse. OP_RETURN gemmer data til eksterne programmer. Noden tilføjer gebyrforespørgsler, kontrol før afsendelse, status for RBF-erstatning og data i blokrækkefølge. Erstatningen valideres, før ventende transaktioner fjernes. Flere signaturer og låste outputs er implementeret til isolerede aktiveringstests; de er endnu ikke aktive på det offentlige netværk.

[API_CONTRACT.json](../../../API_CONTRACT.json)
