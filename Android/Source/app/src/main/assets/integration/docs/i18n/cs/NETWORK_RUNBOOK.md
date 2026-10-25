# SUMUWW Android 0.6.95 · Provoz uzlu

SUMUWW Android 0.6.95 · Uzel ověřuje, ukládá, předává a zpřístupňuje data řetězce.

## Síť a adresy

Veřejná síť je `sumuww`, interní alias `dora`. Ověřte níže uvedený hash genesis. Nativní adresy používají witness v0 P2WPKH a HASH160 komprimovaného veřejného klíče secp256k1. Memo ani tag nejsou povinné. Odmítněte cizí síť a chybný kontrolní součet. Zaznamenejte HD větev příjmu/vratky a index; nepředpokládejte derivační cestu Bitcoinu.

## Vyhledání transakcí a bloků

`getrawtransaction` prohledává aktivní řetězec a mempool, nikoli výhradně osiřelé transakce. Vstupy určují předchozí výstupy, ne jednoznačného odesílatele. `getblock` používá logické `verbose`; uložené neaktivní bloky mají `active=false`, `confirmations=-1`. Surové transakce zůstávají dostupné přes hash bloku. `findspendingtransaction` hledá pouze potvrzené aktivní útraty; null nedokazuje dostupnost. Zkontrolujte `gettxout` s `include_mempool=true`. Potvrzení a aktivní stav se mohou při reorganizaci změnit.

[API_CONTRACT.json](../../../API_CONTRACT.json)
