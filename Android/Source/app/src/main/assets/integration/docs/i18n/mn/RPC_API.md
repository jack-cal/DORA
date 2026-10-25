# SUMUWW Android 0.6.95 · RPC ба HTTP API

SUMUWW Android 0.6.95 · Зангилаа гинжний өгөгдлийг шалгаж, хадгалж, дамжуулж, лавлах боломж олгоно.

API тодорхойлолт нь суулгасан зангилааны цөмийг тайлбарлана. Android аппад RPC тохиргооны дэлгэц байхгүй.

## RPC ба HTTP API

validateaddress шалгах нийлбэр болон сонгосон сүлжээг шалгана. decoderawtransaction-ийн decoded_only нь зөвхөн өгөгдөл тайлсныг заана; гарын үсгийн хүчинтэй байдал эсвэл баталгаажуулалт биш. OP_RETURN гаднын програмд өгөгдөл хадгална. Зангилаанд шимтгэл лавлах, илгээхийн өмнөх шалгалт, RBF орлуулалтын төлөв болон блокийн дарааллаар өгөгдөл унших боломж нэмэв. Хүлээгдэж буй гүйлгээг устгахаас өмнө орлуулах гүйлгээг шалгана. Олон гарын үсэг болон түгжээтэй гаралтыг тусгаарласан идэвхжүүлэлтийн туршилтад хэрэгжүүлсэн; нийтийн сүлжээнд хараахан идэвхжээгүй.

## Дүн ба ашиглах боломжтой гаралт

`_units` нь хамгийн бага нэгжийн бүхэл тоо, `_smw` нь 8 орны бутархайтай текст, `_dora` нь нийцлийн өөр нэр. `_sumuww` дүнгийн талбар байхгүй. 1 SMW = 100000000 нэгж. `gettxout` нь `spendable`-гүй бөгөөд боловсроогүй coinbase гаралт буцааж болно. Дараагийн блокт зарцуулахад дор хаяж 100 баталгаа хэрэгтэй. `listunspent`-ийг `spendable`-аар шүүнэ; `getaddressbalance`-ийн available нь боловсроогүй, хүлээгдэж буй зарлагад орсон хөрөнгийг хасна. Шинэ mempool гаралт батлагдсан хөрөнгө биш. Хуудсуудын хооронд үзүүрийг шалгаж, сонгосон оролтыг дахин батална.

1 SMW = 100,000,000 yugeon. Автомат шимтгэл нь дотоод ажиглалтад тулгуурласан гурван сонголттой бөгөөд баталгаажих хугацааг амлахгүй. yugeon/vB хэмжээг гараар оруулж болно. Илгээхээс өмнө эцсийн шимтгэл болон нийт дүнг SMW-ээр шалгана уу. Татгалзсан гүйлгээ үлдэгдлийг бууруулахгүй.

`1 yugeon = 0.00000001 SMW` · `1 SMW = 100000000 yugeon`

| API / wallet | yugeon / SMW |
|---|---|
| minimum relay | 1 yugeon/vB |
| automatic cap | 0.01 SMW |
| manual cap | 1 SMW |
| manual rate | 1–100000 yugeon/vB |

Автомат шимтгэл нь хүлээгдэж буй өгөгдлийн хэмжээ, блокийн багтаамж, гүйлгээний эрэмбийг тооцно. Өмнөх блокийн шимтгэлийг ашиглахгүй. Хүлээлт бага бол хамгийн бага тариф хэвээр байна. Урьдчилсан дүн шинэчлэгдэж, эцсийн баталгаажуулалтаар шимтгэл тогтоно. Ажиглалт нь холбогдсон дотоод зангилаанд хамаарна, бүх зангилааг хамрахгүй.

Түрийвчийг дахин нээсний дараа ч энэ зангилаанд бүртгэсэн гүйлгээ солигдсон түүх хадгалагдана. Хасагдсан гүйлгээ үлдэгдэлд нөлөөлөхгүй.

Олборлолтын түүх блок бүрийн шинэ гаргалт, гүйлгээний шимтгэл, нийт шагналыг тусад нь харуулна. Таны түрийвчид орсон дүнг мөн тусад нь үзүүлнэ. Шагналыг хэсэгчлэн авсан бол хоёр хэсгийн хуваарилалтыг таамаглахгүй. Зангилаа шимтгэл тооцоолох зэрэг 28 RPC арга өгч, гарын үсэгтэй гүйлгээг шалгаж дамжуулна.

## Гүйлгээ, блок хайх

`getrawtransaction` идэвхтэй хэлхээ, mempool хайна; зөвхөн хаягдсан салаанд байгаа гүйлгээг хайхгүй. Оролт өмнөх гаралтыг заана, ганц илгээгчийн хаяг биш. `getblock` Boolean `verbose` авна; хадгалсан идэвхгүй блок `active=false`, `confirmations=-1` байна. Түүхий гүйлгээг блокийн хэшээр авч болно. `findspendingtransaction` зөвхөн идэвхтэй хэлхээний батлагдсан зарлагыг хайна; null нь ашиглах боломжийн баталгаа биш. `include_mempool=true`-тай `gettxout` шалгана. Баталгаа, идэвхтэй төлөв хэлхээ өөрчлөгдөхөд солигдож болно.

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

[API_CONTRACT.json](../../../API_CONTRACT.json)
