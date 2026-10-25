# SUMUWW · Pagpapatakbo ng node

SUMUWW PC 0.57.46 · Sinusuri, iniimbak, ipinapasa at ipinapakita ng node ang datos ng chain.

## Network at mga address

Ang pampublikong network ay `sumuww`, na may panloob na alyas na `dora`. Suriin ang genesis hash sa ibaba. Gumagamit ang katutubong address ng witness v0 P2WPKH at HASH160 ng compressed secp256k1 public key. Walang kailangang memo o tag. Tanggihan ang maling network at di-wastong checksum. Itala ang HD branch para sa pagtanggap/sukli at index; huwag ipalagay ang derivation path ng Bitcoin.

## Pagpapatunay at mga limitasyon

Tahasang paganahin ang RPC sa numerikong loopback `127.0.0.1:18443` gamit ang pribadong Bearer token. Walang remote signing o pag-unlock ng wallet. Gumamit ng lokal na serbisyo o authenticated tunnel; tinatanggihan ang browser Origin/Referer request. Gumagamit ang JSON-RPC ng POST `/rpc`, object/array `params` at `id`; HTTP 204 ang notification. Limitasyon: body 8004096 byte, header 8192, batch 16, sabay na request 16, takdang oras 10 segundo; limit 1–1000, offset 0–1000000. May 28 method at 11 REST route.

## Paghahanap ng transaksyon at block

Hinahanap ng `getrawtransaction` ang active chain at mempool, hindi ang transaksyong nasa naulilang sangay lamang. Tumutukoy ang input sa dating output, hindi sa iisang sender address. Boolean ang `verbose` ng `getblock`; ang naka-save na inactive block ay may `active=false`, `confirmations=-1`. Maa-access pa rin ang raw transaction sa block hash. Confirmed active spend lamang ang hinahanap ng `findspendingtransaction`; hindi patunay ng availability ang null. Suriin ang `gettxout` na may `include_mempool=true`. Maaaring magbago ang kumpirmasyon at active status sa reorganisasyon.

## Beripikasyon

I-install ang dependencies at patakbuhin ang python examples/node_contract.py mula sa source. Pampublikong test key at pansamantalang regtest ang sumusubok sa pagpapasa, pagtanggi, kumpirmasyon, reorganisasyon at pag-iimbak. Walang totoong pondo, profile ng user o hardware signer na ginagamit.

```text
network: sumuww (dora)
genesis: 00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97
HRP: sumuww
P2P magic: d052470c
1 SMW = 100000000 yugeon
```

[Dokumentasyon](README.html) · [Interface ng node](EXCHANGE_INTEGRATION.html) · [RPC at HTTP API](RPC_API.html) · [Mga tala ng bersyon](RELEASE_NOTES.html) · [Beripikasyon](EXCHANGE_EXAMPLES.html)

[Detalyadong sanggunian sa Ingles](../../../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../../../API_CONTRACT.json) · [vectors.json](../../../../../examples/exchange/vectors.json)
