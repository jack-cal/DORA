# SUMUWW · Provoz uzlu

SUMUWW PC 0.57.46 · Uzel ověřuje, ukládá, předává a zpřístupňuje data řetězce.

## Síť a adresy

Veřejná síť je `sumuww`, interní alias `dora`. Ověřte níže uvedený hash genesis. Nativní adresy používají witness v0 P2WPKH a HASH160 komprimovaného veřejného klíče secp256k1. Memo ani tag nejsou povinné. Odmítněte cizí síť a chybný kontrolní součet. Zaznamenejte HD větev příjmu/vratky a index; nepředpokládejte derivační cestu Bitcoinu.

## Ověření přístupu a limity

RPC zapněte výslovně na číselném loopbacku `127.0.0.1:18443` se soukromým Bearer tokenem. Odemčení peněženky ani vzdálený podpis nejsou zpřístupněny. Použijte místní službu či ověřený tunel; požadavky prohlížeče Origin/Referer se odmítají. JSON-RPC používá POST `/rpc`, objekt/pole `params` a `id`; notifikace vracejí HTTP 204. Limity: tělo 8004096 bajtů, hlavičky 8192, dávka 16, souběžné požadavky 16, lhůta 10 sekund; limit 1–1000, offset 0–1000000. K dispozici je 28 metod a 11 REST cest.

## Vyhledání transakcí a bloků

`getrawtransaction` prohledává aktivní řetězec a mempool, nikoli výhradně osiřelé transakce. Vstupy určují předchozí výstupy, ne jednoznačného odesílatele. `getblock` používá logické `verbose`; uložené neaktivní bloky mají `active=false`, `confirmations=-1`. Surové transakce zůstávají dostupné přes hash bloku. `findspendingtransaction` hledá pouze potvrzené aktivní útraty; null nedokazuje dostupnost. Zkontrolujte `gettxout` s `include_mempool=true`. Potvrzení a aktivní stav se mohou při reorganizaci změnit.

## Ověření

Po instalaci závislostí spusťte ze zdrojů python examples/node_contract.py. Veřejné testovací klíče a dočasný regtest ověřují odeslání, odmítnutí, potvrzení, reorganizaci a uchování dat. Nepoužívají se skutečné prostředky, uživatelské profily ani hardwarové podepisovače.

```text
network: sumuww (dora)
genesis: 00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97
HRP: sumuww
P2P magic: d052470c
1 SMW = 100000000 yugeon
```

[Dokumentace](README.html) · [Rozhraní uzlu](EXCHANGE_INTEGRATION.html) · [RPC a HTTP API](RPC_API.html) · [Poznámky k vydání](RELEASE_NOTES.html) · [Ověření](EXCHANGE_EXAMPLES.html)

[Podrobná anglická reference](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
