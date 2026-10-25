# SUMUWW · RPC और HTTP API

SUMUWW PC 0.57.46 · नोड चेन डेटा की जाँच, संग्रह, प्रसार और जानकारी उपलब्ध कराने का काम करता है।

## RPC और HTTP API

validateaddress चेकसम और चुना गया नेटवर्क जाँचता है। decoderawtransaction का decoded_only केवल डेटा पढ़ने का संकेत है, हस्ताक्षर की वैधता या पुष्टि का नहीं। OP_RETURN आउटपुट बाहरी प्रोग्राम के लिए डेटा रखते हैं. नोड में शुल्क पूछताछ, भेजने से पहले जाँच, RBF प्रतिस्थापन की स्थिति और ब्लॉक क्रम में डेटा पढ़ने की सुविधा जोड़ी गई है। लंबित लेनदेन हटाने से पहले नए लेनदेन की जाँच होती है। बहु-हस्ताक्षर और लॉक किए गए आउटपुट अलग परीक्षणों के लिए लागू हैं; सार्वजनिक नेटवर्क पर अभी सक्रिय नहीं हैं।

## प्रमाणीकरण और सीमाएँ

निजी Bearer token के साथ संख्यात्मक loopback `127.0.0.1:18443` पर RPC स्पष्ट रूप से चालू करें। वॉलेट खोलना या दूरस्थ हस्ताक्षर उपलब्ध नहीं हैं। स्थानीय सेवा या प्रमाणित tunnel उपयोग करें; ब्राउज़र के Origin/Referer अनुरोध अस्वीकार होते हैं। JSON-RPC में POST `/rpc`, object/array `params` और `id` हैं; notification का उत्तर HTTP 204 है। सीमाएँ: body 8004096 बाइट, header 8192, batch 16, समवर्ती अनुरोध 16, समय 10 सेकंड; limit 1–1000, offset 0–1000000। कुल 28 method और 11 REST route हैं।

## राशियाँ और उपलब्ध आउटपुट

`_units` सबसे छोटी इकाई का पूर्णांक है; `_smw` 8 दशमलव का string; `_dora` संगतता उपनाम। `_sumuww` राशि फ़ील्ड नहीं है। 1 SMW = 100000000 इकाइयाँ। `gettxout` में `spendable` नहीं और अपरिपक्व coinbase आउटपुट लौट सकता है। अगले ब्लॉक में खर्च हेतु कम से कम 100 पुष्टियाँ चाहिए। `listunspent` को `spendable` से छाँटें; `getaddressbalance` का available अपरिपक्व और लंबित खर्च में लगे धन को हटाता है। नए mempool आउटपुट पुष्ट धन नहीं हैं। पन्नों के बीच सिरा जाँचें और चुने इनपुट फिर सत्यापित करें।

1 SMW = 100,000,000 yugeon। स्वचालित शुल्क स्थानीय अवलोकनों के आधार पर तीन विकल्प देता है; पुष्टि के समय की गारंटी नहीं है। आप yugeon/vB में दर स्वयं भर सकते हैं। भेजने से पहले अंतिम शुल्क और कुल राशि SMW में जाँचें। अस्वीकार किए गए लेनदेन से शेष राशि नहीं कटती।

`1 yugeon = 0.00000001 SMW` · `1 SMW = 100000000 yugeon`

| API / wallet | yugeon / SMW |
|---|---|
| minimum relay | 1 yugeon/vB |
| automatic cap | 0.01 SMW |
| manual cap | 1 SMW |
| manual rate | 1–100000 yugeon/vB |

स्वचालित शुल्क में लंबित डेटा की मात्रा, ब्लॉक क्षमता और लेनदेन की प्राथमिकता शामिल हैं। पिछले ब्लॉकों के शुल्क इस्तेमाल नहीं होते। कतार छोटी हो तो न्यूनतम दर बनी रहती है। पूर्वावलोकन अद्यतन होता है; अंतिम पुष्टि शुल्क तय करती है। अवलोकन जुड़े हुए स्थानीय नोड के हैं, सभी नोड के नहीं।

वॉलेट दोबारा शुरू करने पर भी इस नोड में दर्ज लेन-देन बदलने का इतिहास बना रहता है। हटाए गए लेन-देन से शेष राशि नहीं बदलती।

खनन इतिहास में प्रत्येक ब्लॉक का नया निर्गम, लेनदेन शुल्क और कुल पुरस्कार अलग दिखते हैं। आपके वॉलेट को मिली राशि अलग दिखाई जाती है। आंशिक दावा होने पर दोनों हिस्सों में राशि का मनमाना बँटवारा नहीं किया जाता। नोड शुल्क अनुमान सहित 28 RPC विधियाँ देता है और हस्ताक्षरित लेनदेन की जाँच तथा प्रसारण करता है।

## लेनदेन और ब्लॉक खोज

`getrawtransaction` सक्रिय चेन और mempool खोजता है, केवल अनाथ शाखा के लेनदेन नहीं। इनपुट पुराने आउटपुट बताते हैं, एक निश्चित प्रेषक पता नहीं। `getblock` का `verbose` Boolean है; सहेजे निष्क्रिय ब्लॉक में `active=false`, `confirmations=-1` होता है। उनका कच्चा लेनदेन ब्लॉक hash से मिलता रहता है। `findspendingtransaction` केवल सक्रिय चेन के पुष्ट खर्च खोजता है; null उपलब्धता का प्रमाण नहीं। `include_mempool=true` के साथ `gettxout` देखें। पुनर्गठन में पुष्टि और सक्रिय स्थिति बदल सकती हैं।

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

[दस्तावेज़](README.html) · [नोड इंटरफ़ेस](EXCHANGE_INTEGRATION.html) · [नोड संचालन](NETWORK_RUNBOOK.html) · [संस्करण टिप्पणियाँ](RELEASE_NOTES.html) · [सत्यापन](EXCHANGE_EXAMPLES.html)

[विस्तृत अंग्रेज़ी संदर्भ](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
