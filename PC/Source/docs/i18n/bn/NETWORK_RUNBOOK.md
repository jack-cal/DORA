# SUMUWW · নোড পরিচালনা

SUMUWW PC 0.57.46 · নোড চেইনের তথ্য যাচাই, সংরক্ষণ, প্রচার ও খোঁজার সুবিধা দেয়।

## নেটওয়ার্ক ও ঠিকানা

সর্বজনীন নেটওয়ার্ক `sumuww`, অভ্যন্তরীণ নাম `dora`। নিচের genesis hash মিলিয়ে দেখুন। মূল ঠিকানা witness v0 P2WPKH এবং সংকুচিত secp256k1 পাবলিক কির HASH160 ব্যবহার করে। বাধ্যতামূলক memo বা tag নেই। ভুল নেটওয়ার্ক ও অবৈধ checksum প্রত্যাখ্যান করুন। HD গ্রহণ/ফেরত শাখা ও index লিখে রাখুন; Bitcoin-এর derivation path ধরে নেবেন না।

## প্রমাণীকরণ ও সীমা

ব্যক্তিগত Bearer token দিয়ে সংখ্যাসূচক loopback `127.0.0.1:18443`-এ RPC স্পষ্টভাবে চালু করুন। ওয়ালেট খোলা বা দূরবর্তী স্বাক্ষর নেই। স্থানীয় সেবা বা প্রমাণীকৃত tunnel ব্যবহার করুন; ব্রাউজারের Origin/Referer অনুরোধ প্রত্যাখ্যাত হয়। JSON-RPC-তে POST `/rpc`, object/array `params` ও `id`; notification-এ HTTP 204। সীমা: body 8004096 বাইট, header 8192, batch 16, একসঙ্গে অনুরোধ 16, সময় 10 সেকেন্ড; limit 1–1000, offset 0–1000000। মোট 28 method ও 11 REST route।

## লেনদেন ও ব্লক খোঁজা

`getrawtransaction` সক্রিয় চেইন ও mempool খোঁজে, শুধু বিচ্ছিন্ন শাখায় থাকা লেনদেন নয়। ইনপুট আগের আউটপুট নির্দেশ করে, একটিমাত্র প্রেরকের ঠিকানা নয়। `getblock`-এর `verbose` Boolean; সংরক্ষিত নিষ্ক্রিয় ব্লকে `active=false`, `confirmations=-1`। ব্লক hash দিয়ে কাঁচা লেনদেন পাওয়া যায়। `findspendingtransaction` শুধু সক্রিয় চেইনের নিশ্চিত খরচ খোঁজে; null ব্যবহারযোগ্যতার প্রমাণ নয়। `include_mempool=true` দিয়ে `gettxout` দেখুন। পুনর্গঠনে নিশ্চয়তা ও সক্রিয় অবস্থা বদলাতে পারে।

## যাচাই

নির্ভরতা ইনস্টল করে সোর্স থেকে python examples/node_contract.py চালান। প্রকাশ্য পরীক্ষার চাবি ও অস্থায়ী regtest দিয়ে জমা, প্রত্যাখ্যান, নিশ্চিতকরণ, পুনর্গঠন ও তথ্য সংরক্ষণ পরীক্ষা হয়। আসল অর্থ, ব্যবহারকারী প্রোফাইল বা হার্ডওয়্যার স্বাক্ষরকারী ব্যবহার হয় না।

```text
network: sumuww (dora)
genesis: 00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97
HRP: sumuww
P2P magic: d052470c
1 SMW = 100000000 yugeon
```

[নথিপত্র](README.html) · [নোড ইন্টারফেস](EXCHANGE_INTEGRATION.html) · [RPC ও HTTP API](RPC_API.html) · [সংস্করণের বিবরণ](RELEASE_NOTES.html) · [যাচাই](EXCHANGE_EXAMPLES.html)

[বিস্তারিত ইংরেজি নির্দেশিকা](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
