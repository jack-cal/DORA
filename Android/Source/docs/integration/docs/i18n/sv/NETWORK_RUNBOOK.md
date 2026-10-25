# SUMUWW Android 0.6.95 · Noddrift

SUMUWW Android 0.6.95 · Noden validerar, lagrar, vidarebefordrar och tillhandahåller kedjedata.

## Nätverk och adresser

Det publika nätverket heter `sumuww`, internt även `dora`. Kontrollera genesis-hashen nedan. Adresser använder witness v0 P2WPKH och HASH160 av en komprimerad secp256k1-nyckel. Memo eller tagg krävs inte. Avvisa fel nätverk och ogiltiga kontrollsummor. Anteckna HD-gren för mottagning/växel och index; anta inte Bitcoins härledningsväg.

## Sök transaktioner och block

`getrawtransaction` söker aktiv kedja och mempool, inte enbart övergivna transaktioner. Ingångar anger tidigare utgångar, inte en unik avsändare. `getblock` tar boolesk `verbose`; lagrade inaktiva block har `active=false`, `confirmations=-1`. Råtransaktioner kan fortsatt hämtas via blockhash. `findspendingtransaction` söker bara bekräftade aktiva utgifter; null bevisar inte tillgänglighet. Kontrollera `gettxout` med `include_mempool=true`. Bekräftelser och aktiv status kan ändras vid omorganisation.

[API_CONTRACT.json](../../../API_CONTRACT.json)
