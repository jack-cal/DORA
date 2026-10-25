# SUMUWW · RPC at HTTP API

SUMUWW PC 0.57.46 · Sinusuri, iniimbak, ipinapasa at ipinapakita ng node ang datos ng chain.

## RPC at HTTP API

Sinusuri ng validateaddress ang checksum at napiling network. Ang decoded_only mula sa decoderawtransaction ay pagbasa lang ng datos, hindi patunay ng wastong lagda o kumpirmasyon. Nag-iimbak ang OP_RETURN ng datos para sa panlabas na programa. May dagdag na pagtatanong ng bayad, pagsusuri bago magpadala, katayuan ng pagpapalit sa RBF at datos ayon sa pagkakasunod ng mga block. Sinusuri muna ang kapalit bago alisin ang mga nakabinbing transaksiyon. Naipatupad ang maramihang lagda at naka-lock na output para sa hiwalay na pagsubok; hindi pa aktibo sa pampublikong network.

## Pagpapatunay at mga limitasyon

Tahasang paganahin ang RPC sa numerikong loopback `127.0.0.1:18443` gamit ang pribadong Bearer token. Walang remote signing o pag-unlock ng wallet. Gumamit ng lokal na serbisyo o authenticated tunnel; tinatanggihan ang browser Origin/Referer request. Gumagamit ang JSON-RPC ng POST `/rpc`, object/array `params` at `id`; HTTP 204 ang notification. Limitasyon: body 8004096 byte, header 8192, batch 16, sabay na request 16, takdang oras 10 segundo; limit 1–1000, offset 0–1000000. May 28 method at 11 REST route.

## Halaga at magagamit na output

Ang `_units` ay integer sa pinakamaliit na yunit; `_smw` ay string na may 8 decimal; `_dora` ay compatibility alias. Walang amount field na `_sumuww`. 1 SMW = 100000000 yunit. Walang `spendable` ang `gettxout` at maaaring magbalik ng hindi pa hinog na coinbase output. Kailangan ng hindi bababa sa 100 kumpirmasyon para gastusin sa susunod na block. Salain ang `listunspent` sa `spendable`; hindi kasama sa available ng `getaddressbalance` ang hindi pa hinog at nakatali sa pending spend. Hindi kumpirmado ang bagong mempool output. Suriin ang dulo sa pagitan ng mga pahina at muling patunayan ang piniling input.

1 SMW = 100,000,000 yugeon. May tatlong antas ang awtomatikong bayad batay sa lokal na obserbasyon, ngunit walang garantisadong oras ng kumpirmasyon. Maaari kang magtakda ng rate sa yugeon/vB. Suriin ang huling bayad at kabuuang SMW bago magpadala. Hindi nababawasan ang balanse sa tinanggihang transaksiyon.

`1 yugeon = 0.00000001 SMW` · `1 SMW = 100000000 yugeon`

| API / wallet | yugeon / SMW |
|---|---|
| minimum relay | 1 yugeon/vB |
| automatic cap | 0.01 SMW |
| manual cap | 1 SMW |
| manual rate | 1–100000 yugeon/vB |

Batay ang awtomatikong bayad sa dami ng nakabinbing datos, kapasidad ng bloke at prayoridad ng transaksiyon. Hindi ginagamit ang bayad ng mga nakaraang bloke. Kapag maikli ang pila, nananatili ang pinakamababang singil. Naa-update ang preview; itinatakda ng huling kumpirmasyon ang bayad. Ang obserbasyon ay para sa nakakonektang lokal na node, hindi sa lahat ng node.

Nananatili ang tala ng mga pagpapalit na naitala ng node na ito kahit i-restart ang wallet. Hindi naaapektuhan ng mga inalis na transaksiyon ang balanse.

Hiwalay sa kasaysayan ng pagmimina ang bagong inilabas, bayarin sa transaksyon, at kabuuang gantimpala ng bawat block. Hiwalay ding ipinapakita ang natanggap ng iyong wallet. Kapag bahagi lamang ang kinuha, hindi ipinapalagay ang paghahati ng dalawang sangkap. May 28 RPC method ang node, kabilang ang pagtatantiya ng bayarin, at sinusuri at ipinapasa nito ang mga nilagdaang transaksyon.

## Paghahanap ng transaksyon at block

Hinahanap ng `getrawtransaction` ang active chain at mempool, hindi ang transaksyong nasa naulilang sangay lamang. Tumutukoy ang input sa dating output, hindi sa iisang sender address. Boolean ang `verbose` ng `getblock`; ang naka-save na inactive block ay may `active=false`, `confirmations=-1`. Maa-access pa rin ang raw transaction sa block hash. Confirmed active spend lamang ang hinahanap ng `findspendingtransaction`; hindi patunay ng availability ang null. Suriin ang `gettxout` na may `include_mempool=true`. Maaaring magbago ang kumpirmasyon at active status sa reorganisasyon.

| method | params |
|---|---|
| `getblockchaininfo` | `{} / []` |
| `gethtlcinfo` | `{} / []` |
| `getspendinginfo` | `{} / []` |
| `getdatarecords` | `blockhash, offset=0, limit=100` |
| `decodescript` | `hex` |
| `gettxout` | `txid, index, include_mempool=true` |
| `findspendingtransaction` | `txid, index, start_height=0` |
| `getnetworkinfo` | `{} / []` |
| `getblockcount` | `{} / []` |
| `getbestblockhash` | `{} / []` |
| `getblockhash` | `height` |
| `getblock` | `hash, verbose=true` |
| `getrawmempool` | `{} / []` |
| `getmempoolinfo` | `{} / []` |
| `getmempoolpolicy` | `{} / []` |
| `estimatefee` | `vsize=140, mode=normal` |
| `testmempoolaccept` | `hex` |
| `getmempoolentry` | `txid` |
| `gettransactionstatus` | `txid` |
| `getrawtransaction` | `txid, verbose=true` |
| `decoderawtransaction` | `hex` |
| `validateaddress` | `address` |
| `listunspent` | `address, limit=100, offset=0` |
| `getaddressbalance` | `address` |
| `sendrawtransaction` | `hex` |
| `submitblock` | `hex` |
| `getblocktemplate` | `address` |
| `help` | `{} / []` |

| HTTP | URI | JSON |
|---|---|---|
| `GET` | `/api/v1/info` | `—` |
| `GET` | `/api/v1/network` | `—` |
| `GET` | `/api/v1/mempool` | `—` |
| `GET` | `/api/v1/mempool/info` | `—` |
| `GET` | `/api/v1/blocks/{height-or-hash}` | `—` |
| `GET` | `/api/v1/transactions/{txid}` | `—` |
| `GET` | `/api/v1/addresses/{address}/balance` | `—` |
| `GET` | `/api/v1/addresses/{address}/utxos?limit=100&offset=0` | `—` |
| `POST` | `/api/v1/transactions` | `{"hex":"..."}` |
| `POST` | `/api/v1/blocks` | `{"hex":"..."}` |
| `POST` | `/api/v1/mining/template` | `{"address":"..."}` |

[Dokumentasyon](README.html) · [Interface ng node](EXCHANGE_INTEGRATION.html) · [Pagpapatakbo ng node](NETWORK_RUNBOOK.html) · [Mga tala ng bersyon](RELEASE_NOTES.html) · [Beripikasyon](EXCHANGE_EXAMPLES.html)

[Detalyadong sanggunian sa Ingles](../../../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../../../API_CONTRACT.json) · [vectors.json](../../../../../examples/exchange/vectors.json)
