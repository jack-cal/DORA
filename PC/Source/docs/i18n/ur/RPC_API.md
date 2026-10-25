# SUMUWW · RPC اور HTTP API

SUMUWW PC 0.57.46 · نوڈ چین کے ڈیٹا کی تصدیق، حفاظت، ترسیل اور استفسار فراہم کرتا ہے۔

## RPC اور HTTP API

validateaddress چیک سم اور منتخب نیٹ ورک جانچتا ہے۔ decoderawtransaction میں decoded_only صرف ڈیٹا پڑھنے کو ظاہر کرتا ہے، دستخط کی صحت یا تصدیق کو نہیں۔ OP_RETURN بیرونی پروگراموں کے لیے ڈیٹا رکھتا ہے. نوڈ میں فیس کی معلومات، بھیجنے سے پہلے جانچ، RBF تبدیلی کی حالت اور بلاک کی ترتیب سے ڈیٹا پڑھنے کی سہولت شامل ہے۔ زیرِ التوا ٹرانزیکشن ہٹانے سے پہلے متبادل کی جانچ ہوتی ہے۔ متعدد دستخط اور مقفل آؤٹ پٹ الگ ماحول میں فعال کرنے کی آزمائش کے لیے تیار ہیں؛ عوامی نیٹ ورک پر ابھی فعال نہیں۔

## توثیق اور حدود

نجی Bearer token کے ساتھ عددی loopback `127.0.0.1:18443` پر RPC واضح طور پر فعال کریں۔ والٹ کھولنا یا دور سے دستخط دستیاب نہیں۔ مقامی خدمت یا تصدیق شدہ tunnel استعمال کریں؛ براؤزر کی Origin/Referer درخواست مسترد ہوتی ہے۔ JSON-RPC میں POST `/rpc`، object/array `params` اور `id` ہیں؛ notification پر HTTP 204 ملتا ہے۔ حدود: body 8004096 بائٹ، header 8192، batch 16، بیک وقت درخواستیں 16، وقت 10 سیکنڈ؛ limit 1–1000، offset 0–1000000۔ کل 28 method اور 11 REST route ہیں۔

## رقم اور دستیاب آؤٹ پٹ

`_units` سب سے چھوٹی اکائی کا صحیح عدد، `_smw` آٹھ اعشاری جگہوں کا متن، `_dora` مطابقتی نام ہے۔ `_sumuww` رقم کا خانہ نہیں۔ 1 SMW = 100000000 اکائیاں۔ `gettxout` میں `spendable` نہیں اور ناپختہ coinbase آؤٹ پٹ آ سکتا ہے۔ اگلے بلاک میں خرچ کے لیے کم از کم 100 تصدیقیں چاہییں۔ `listunspent` کو `spendable` سے چھانٹیں؛ `getaddressbalance` کا available ناپختہ اور منتظر خرچ میں بندھی رقم نکالتا ہے۔ نئے mempool آؤٹ پٹ تصدیق شدہ نہیں۔ صفحات کے درمیان سرا جانچیں، منتخب ان پٹ دوبارہ پرکھیں۔

1 SMW = 100,000,000 yugeon۔ خودکار فیس مقامی مشاہدات کی بنیاد پر تین درجے دیتی ہے، مگر تصدیق کے وقت کی ضمانت نہیں۔ آپ yugeon/vB میں شرح خود درج کر سکتے ہیں۔ بھیجنے سے پہلے آخری فیس اور کل رقم SMW میں دیکھیں۔ مسترد ہونے والی ٹرانزیکشن سے بیلنس نہیں کٹتا۔

`1 yugeon = 0.00000001 SMW` · `1 SMW = 100000000 yugeon`

| API / wallet | yugeon / SMW |
|---|---|
| minimum relay | 1 yugeon/vB |
| automatic cap | 0.01 SMW |
| manual cap | 1 SMW |
| manual rate | 1–100000 yugeon/vB |

خودکار فیس زیرِ انتظار ڈیٹا کی مقدار، بلاک کی گنجائش اور لین دین کی ترجیح کے مطابق ہوتی ہے۔ پچھلے بلاکوں کی فیس استعمال نہیں ہوتی۔ قطار مختصر ہو تو کم از کم شرح برقرار رہتی ہے۔ پیش نظارہ تازہ ہوتا ہے؛ آخری تصدیق پر فیس مقرر ہو جاتی ہے۔ مشاہدات صرف منسلک مقامی نوڈ کے ہیں، تمام نوڈز کے نہیں۔

والیٹ دوبارہ کھولنے پر بھی اس نوڈ میں درج لین دین کی تبدیلیوں کا ریکارڈ برقرار رہتا ہے۔ ہٹائے گئے لین دین بیلنس پر اثر نہیں ڈالتے۔

مائننگ کی تاریخ ہر بلاک کا نیا اجرا، لین دین کی فیس اور کل انعام الگ دکھاتی ہے۔ آپ کے والیٹ کو موصول رقم الگ ظاہر ہوتی ہے۔ جزوی وصولی پر دونوں حصوں کی تقسیم فرض نہیں کی جاتی۔ نوڈ فیس کے تخمینے سمیت 28 RPC طریقے فراہم کرتا ہے اور دستخط شدہ لین دین کی توثیق اور ترسیل کرتا ہے۔

## لین دین اور بلاک کی تلاش

`getrawtransaction` فعال چین اور mempool تلاش کرتا ہے، صرف الگ شاخ میں موجود لین دین نہیں۔ ان پٹ پچھلے آؤٹ پٹ بتاتا ہے، ایک منفرد بھیجنے والا پتہ نہیں۔ `getblock` کا `verbose` Boolean ہے؛ محفوظ غیر فعال بلاک میں `active=false` اور `confirmations=-1` ہیں۔ خام لین دین بلاک hash سے اب بھی ملتا ہے۔ `findspendingtransaction` صرف فعال چین کے تصدیق شدہ خرچ تلاش کرتا ہے؛ null دستیابی کا ثبوت نہیں۔ `include_mempool=true` کے ساتھ `gettxout` دیکھیں۔ تنظیم نو میں تصدیقیں اور فعال حالت بدل سکتی ہیں۔

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

[دستاویزات](README.html) · [نوڈ انٹرفیس](EXCHANGE_INTEGRATION.html) · [نوڈ چلانا](NETWORK_RUNBOOK.html) · [نسخے کی تفصیل](RELEASE_NOTES.html) · [جانچ](EXCHANGE_EXAMPLES.html)

[تفصیلی انگریزی حوالہ](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
