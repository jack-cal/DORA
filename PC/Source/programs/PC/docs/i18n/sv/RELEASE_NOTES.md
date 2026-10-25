# SUMUWW · Versionsinformation

SUMUWW PC 0.57.46 · Noden validerar, lagrar, vidarebefordrar och tillhandahåller kedjedata.

## Signeringsformat

Det valfria källkods-SDK:t sammanställer transaktioner och verifierar tillhandahållna signaturer utan nycklar eller nätverk. Det är inget signeringsprogram eller nodkommando. P2WPKH-begränsningen gäller exempelformatet, inte noden. Den personliga plånboken finns kvar.

## RPC- och HTTP-API

validateaddress kontrollerar kontrollsumman och det valda nätverket. decoderawtransaction ger decoded_only, inget bevis på giltig signatur eller bekräftelse. OP_RETURN bevarar data för externa program. Noden lägger till avgiftsfrågor, kontroll före sändning, status för RBF-ersättning och data i blockordning. Ersättningen valideras innan väntande transaktioner tas bort. Flera signaturer och låsta utdata är implementerade för isolerade aktiveringstester; de är ännu inte aktiva i det offentliga nätverket.

## Verifiering

Installera beroendena och kör python examples/node_contract.py från källkoden. Offentliga testnycklar och tillfälligt regtest prövar insändning, avvisning, bekräftelser, omorganisation och lagring. Inga riktiga medel, användarprofiler eller hårdvarusignerare används.

[Dokumentation](README.html) · [Nodgränssnitt](EXCHANGE_INTEGRATION.html) · [RPC- och HTTP-API](RPC_API.html) · [Noddrift](NETWORK_RUNBOOK.html) · [Verifiering](EXCHANGE_EXAMPLES.html)

[Utförlig engelsk referens](../../../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../../../API_CONTRACT.json) · [vectors.json](../../../../../examples/exchange/vectors.json)
