# SUMUWW Android 0.6.95 · নোড পরিচালনা

SUMUWW Android 0.6.95 · নোড চেইনের তথ্য যাচাই, সংরক্ষণ, প্রচার ও খোঁজার সুবিধা দেয়।

## নেটওয়ার্ক ও ঠিকানা

সর্বজনীন নেটওয়ার্ক `sumuww`, অভ্যন্তরীণ নাম `dora`। নিচের genesis hash মিলিয়ে দেখুন। মূল ঠিকানা witness v0 P2WPKH এবং সংকুচিত secp256k1 পাবলিক কির HASH160 ব্যবহার করে। বাধ্যতামূলক memo বা tag নেই। ভুল নেটওয়ার্ক ও অবৈধ checksum প্রত্যাখ্যান করুন। HD গ্রহণ/ফেরত শাখা ও index লিখে রাখুন; Bitcoin-এর derivation path ধরে নেবেন না।

## লেনদেন ও ব্লক খোঁজা

`getrawtransaction` সক্রিয় চেইন ও mempool খোঁজে, শুধু বিচ্ছিন্ন শাখায় থাকা লেনদেন নয়। ইনপুট আগের আউটপুট নির্দেশ করে, একটিমাত্র প্রেরকের ঠিকানা নয়। `getblock`-এর `verbose` Boolean; সংরক্ষিত নিষ্ক্রিয় ব্লকে `active=false`, `confirmations=-1`। ব্লক hash দিয়ে কাঁচা লেনদেন পাওয়া যায়। `findspendingtransaction` শুধু সক্রিয় চেইনের নিশ্চিত খরচ খোঁজে; null ব্যবহারযোগ্যতার প্রমাণ নয়। `include_mempool=true` দিয়ে `gettxout` দেখুন। পুনর্গঠনে নিশ্চয়তা ও সক্রিয় অবস্থা বদলাতে পারে।

[API_CONTRACT.json](../../../API_CONTRACT.json)
