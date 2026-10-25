# SUMUWW · واجهة RPC وHTTP

SUMUWW PC 0.57.46 · تتحقق العقدة من بيانات السلسلة وتحفظها وتنشرها وتتيح الاستعلام عنها.

## واجهة RPC وHTTP

يتحقق validateaddress من المجموع الاختباري والشبكة المحددة. تعني decoded_only في decoderawtransaction فك البيانات فقط، ولا تثبت صحة التوقيع أو التأكيد. تحفظ مخرجات OP_RETURN بيانات للبرامج الخارجية. أضيفت إلى العقدة استعلامات الرسوم والفحص قبل الإرسال وحالة الاستبدال RBF وقراءة بيانات الكتل بالترتيب. يُتحقق من المعاملة البديلة قبل حذف أي معاملة معلقة. نُفذت التوقيعات المتعددة والمخرجات المقفلة لاختبارات تفعيل معزولة، ولم تُفعّل بعد على الشبكة العامة.

## المصادقة والحدود

فعّل RPC صراحة على عنوان loopback الرقمي `127.0.0.1:18443` باستخدام رمز Bearer خاص. لا تُتاح عملية فتح المحفظة أو التوقيع البعيد. استخدم خدمة محلية أو نفقًا موثّقًا؛ تُرفض طلبات المتصفح ذات Origin/Referer. يستخدم JSON-RPC طلب POST `/rpc` و`params` ككائن/مصفوفة و`id`؛ تعيد الإشعارات HTTP 204. الحدود: جسم 8004096 بايت، رؤوس 8192، دفعة 16، طلبات متزامنة 16، مهلة 10 ثوانٍ؛ limit من 1–1000 وoffset من 0–1000000. توجد 28 طريقة و11 مسار REST.

## المبالغ والمخرجات المتاحة

`_units` عدد صحيح لأصغر الوحدات، و`_smw` نص ذو 8 خانات عشرية، و`_dora` اسم بديل للتوافق. لا يوجد حقل مبلغ `_sumuww`. كل 1 SMW يساوي 100000000 وحدة. لا يحتوي `gettxout` على `spendable` وقد يعيد مخرجات coinbase غير ناضجة. يلزم 100 تأكيد على الأقل للصرف في الكتلة التالية. رشّح `listunspent` حسب `spendable`؛ مبلغ available في `getaddressbalance` يستبعد الأموال غير الناضجة أو المستخدمة في إنفاق معلّق. مخرجات mempool الجديدة ليست مؤكدة. افحص القمة بين الصفحات وأعد التحقق من المدخلات المختارة.

1 SMW = 100,000,000 yugeon. تقترح الرسوم التلقائية ثلاثة مستويات استنادًا إلى البيانات المحلية، دون ضمان وقت التأكيد. يمكنك إدخال المعدل يدويًا بوحدة yugeon/vB. راجع الرسوم النهائية والمجموع بوحدة SMW قبل الإرسال. لا تُخصم المعاملة المرفوضة من رصيدك.

`1 yugeon = 0.00000001 SMW` · `1 SMW = 100000000 yugeon`

| API / wallet | yugeon / SMW |
|---|---|
| minimum relay | 1 yugeon/vB |
| automatic cap | 0.01 SMW |
| manual cap | 1 SMW |
| manual rate | 1–100000 yugeon/vB |

تراعي الرسوم التلقائية حجم البيانات المنتظرة وسعة الكتل وأولوية المعاملات. لا تستخدم رسوم الكتل السابقة. عند قلة الانتظار يبقى المعدل الأدنى. تتجدد المعاينة، ويثبت التأكيد النهائي قيمة الرسوم. تشمل المراقبة العقدة المحلية المتصلة، لا جميع العقد.

يحتفظ سجل المحفظة بالاستبدالات التي رصدتها هذه العقدة بعد إعادة التشغيل. لا تؤثر المعاملات المحذوفة على الرصيد.

يفصل سجل التعدين بين الإصدار الجديد ورسوم المعاملات وإجمالي مكافأة كل كتلة. يظهر المبلغ الذي تلقته محفظتك بشكل منفصل. عند المطالبة بجزء من المكافأة، لا يُفترض توزيع المبلغ بين المكونين. توفر العقدة 28 طريقة RPC، بما فيها تقدير الرسوم، وتتحقق من المعاملات الموقعة وتنقلها.

## البحث عن المعاملات والكتل

يبحث `getrawtransaction` في السلسلة النشطة وmempool، لا في معاملات الفروع اليتيمة وحدها. تشير المدخلات إلى مخرجات سابقة، لا إلى عنوان مرسل وحيد. يأخذ `getblock` قيمة `verbose` منطقية؛ الكتل المخزنة غير النشطة لها `active=false` و`confirmations=-1`. تبقى معاملاتها الخام متاحة بتجزئة الكتلة. يبحث `findspendingtransaction` عن الإنفاق المؤكد النشط فقط؛ null لا يثبت التوفر. افحص `gettxout` مع `include_mempool=true`. قد تتغير التأكيدات والحالة النشطة بعد إعادة التنظيم.

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

[الوثائق](README.html) · [واجهة العقدة](EXCHANGE_INTEGRATION.html) · [تشغيل العقدة](NETWORK_RUNBOOK.html) · [ملاحظات الإصدار](RELEASE_NOTES.html) · [التحقق](EXCHANGE_EXAMPLES.html)

[المرجع الإنجليزي المفصل](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
