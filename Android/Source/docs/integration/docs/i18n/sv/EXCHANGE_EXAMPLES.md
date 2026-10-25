# SUMUWW Android 0.6.95 · Verifiering

SUMUWW Android 0.6.95 · Noden validerar, lagrar, vidarebefordrar och tillhandahåller kedjedata.

API-specifikationen beskriver den inbyggda nodkärnan. Android-appen saknar skärm för RPC-inställningar.

## RPC- och HTTP-API

validateaddress kontrollerar kontrollsumman och det valda nätverket. decoderawtransaction ger decoded_only, inget bevis på giltig signatur eller bekräftelse. OP_RETURN bevarar data för externa program. Noden lägger till avgiftsfrågor, kontroll före sändning, status för RBF-ersättning och data i blockordning. Ersättningen valideras innan väntande transaktioner tas bort. Flera signaturer och låsta utdata är implementerade för isolerade aktiveringstester; de är ännu inte aktiva i det offentliga nätverket.

## Sök transaktioner och block

`getrawtransaction` söker aktiv kedja och mempool, inte enbart övergivna transaktioner. Ingångar anger tidigare utgångar, inte en unik avsändare. `getblock` tar boolesk `verbose`; lagrade inaktiva block har `active=false`, `confirmations=-1`. Råtransaktioner kan fortsatt hämtas via blockhash. `findspendingtransaction` söker bara bekräftade aktiva utgifter; null bevisar inte tillgänglighet. Kontrollera `gettxout` med `include_mempool=true`. Bekräftelser och aktiv status kan ändras vid omorganisation.

[API_CONTRACT.json](../../../API_CONTRACT.json)
