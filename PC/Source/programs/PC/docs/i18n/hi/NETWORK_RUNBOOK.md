# SUMUWW · नोड संचालन

SUMUWW PC 0.57.46 · नोड चेन डेटा की जाँच, संग्रह, प्रसार और जानकारी उपलब्ध कराने का काम करता है।

## नेटवर्क और पते

सार्वजनिक नेटवर्क `sumuww` है; उसका आंतरिक उपनाम `dora` है। नीचे दिया genesis hash जाँचें। मूल पते witness v0 P2WPKH और संपीड़ित secp256k1 सार्वजनिक कुंजी का HASH160 इस्तेमाल करते हैं। memo या tag अनिवार्य नहीं है। गलत नेटवर्क और अमान्य checksum अस्वीकार करें। HD प्राप्ति/वापसी शाखा और index दर्ज करें; Bitcoin का derivation path लागू न मानें।

## प्रमाणीकरण और सीमाएँ

निजी Bearer token के साथ संख्यात्मक loopback `127.0.0.1:18443` पर RPC स्पष्ट रूप से चालू करें। वॉलेट खोलना या दूरस्थ हस्ताक्षर उपलब्ध नहीं हैं। स्थानीय सेवा या प्रमाणित tunnel उपयोग करें; ब्राउज़र के Origin/Referer अनुरोध अस्वीकार होते हैं। JSON-RPC में POST `/rpc`, object/array `params` और `id` हैं; notification का उत्तर HTTP 204 है। सीमाएँ: body 8004096 बाइट, header 8192, batch 16, समवर्ती अनुरोध 16, समय 10 सेकंड; limit 1–1000, offset 0–1000000। कुल 28 method और 11 REST route हैं।

## लेनदेन और ब्लॉक खोज

`getrawtransaction` सक्रिय चेन और mempool खोजता है, केवल अनाथ शाखा के लेनदेन नहीं। इनपुट पुराने आउटपुट बताते हैं, एक निश्चित प्रेषक पता नहीं। `getblock` का `verbose` Boolean है; सहेजे निष्क्रिय ब्लॉक में `active=false`, `confirmations=-1` होता है। उनका कच्चा लेनदेन ब्लॉक hash से मिलता रहता है। `findspendingtransaction` केवल सक्रिय चेन के पुष्ट खर्च खोजता है; null उपलब्धता का प्रमाण नहीं। `include_mempool=true` के साथ `gettxout` देखें। पुनर्गठन में पुष्टि और सक्रिय स्थिति बदल सकती हैं।

## सत्यापन

निर्भरताएँ स्थापित करके सोर्स से python examples/node_contract.py चलाएँ। सार्वजनिक परीक्षण कुंजियाँ और अस्थायी regtest भेजना, अस्वीकृति, पुष्टि, पुनर्गठन और डेटा बने रहने की जाँच करते हैं। वास्तविक धन, उपयोगकर्ता प्रोफ़ाइल या हार्डवेयर हस्ताक्षरकर्ता इस्तेमाल नहीं होते।

```text
network: sumuww (dora)
genesis: 00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97
HRP: sumuww
P2P magic: d052470c
1 SMW = 100000000 yugeon
```

[दस्तावेज़](README.html) · [नोड इंटरफ़ेस](EXCHANGE_INTEGRATION.html) · [RPC और HTTP API](RPC_API.html) · [संस्करण टिप्पणियाँ](RELEASE_NOTES.html) · [सत्यापन](EXCHANGE_EXAMPLES.html)

[विस्तृत अंग्रेज़ी संदर्भ](../../../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../../../API_CONTRACT.json) · [vectors.json](../../../../../examples/exchange/vectors.json)
