# SUMUWW Android 0.6.95 · Interface ng node

SUMUWW Android 0.6.95 · Sinusuri, iniimbak, ipinapasa at ipinapakita ng node ang datos ng chain.

Inilalarawan ng API specification ang nakapaloob na node core. Walang screen ng RPC configuration ang Android app.

## Network at mga address

Ang pampublikong network ay `sumuww`, na may panloob na alyas na `dora`. Suriin ang genesis hash sa ibaba. Gumagamit ang katutubong address ng witness v0 P2WPKH at HASH160 ng compressed secp256k1 public key. Walang kailangang memo o tag. Tanggihan ang maling network at di-wastong checksum. Itala ang HD branch para sa pagtanggap/sukli at index; huwag ipalagay ang derivation path ng Bitcoin.

## RPC at HTTP API

Sinusuri ng validateaddress ang checksum at napiling network. Ang decoded_only mula sa decoderawtransaction ay pagbasa lang ng datos, hindi patunay ng wastong lagda o kumpirmasyon. Nag-iimbak ang OP_RETURN ng datos para sa panlabas na programa. May dagdag na pagtatanong ng bayad, pagsusuri bago magpadala, katayuan ng pagpapalit sa RBF at datos ayon sa pagkakasunod ng mga block. Sinusuri muna ang kapalit bago alisin ang mga nakabinbing transaksiyon. Naipatupad ang maramihang lagda at naka-lock na output para sa hiwalay na pagsubok; hindi pa aktibo sa pampublikong network.

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

[API_CONTRACT.json](../../../API_CONTRACT.json)
