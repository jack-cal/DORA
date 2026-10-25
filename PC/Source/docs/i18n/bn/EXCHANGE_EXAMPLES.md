# SUMUWW · যাচাই

SUMUWW PC 0.57.46 · নোড চেইনের তথ্য যাচাই, সংরক্ষণ, প্রচার ও খোঁজার সুবিধা দেয়।

## স্বাক্ষরের বিন্যাস

ঐচ্ছিক সোর্স SDK চাবি বা নেটওয়ার্ক ছাড়াই লেনদেন তৈরি করে এবং দেওয়া স্বাক্ষর যাচাই করে। এটি স্বাক্ষরকারী প্রোগ্রাম বা নোড কমান্ড নয়। P2WPKH সীমা উদাহরণের ফরম্যাটে প্রযোজ্য, নোডে নয়। আগের ব্যক্তিগত ওয়ালেট ব্যবহার করা যাবে।

## যাচাই

নির্ভরতা ইনস্টল করে সোর্স থেকে python examples/node_contract.py চালান। প্রকাশ্য পরীক্ষার চাবি ও অস্থায়ী regtest দিয়ে জমা, প্রত্যাখ্যান, নিশ্চিতকরণ, পুনর্গঠন ও তথ্য সংরক্ষণ পরীক্ষা হয়। আসল অর্থ, ব্যবহারকারী প্রোফাইল বা হার্ডওয়্যার স্বাক্ষরকারী ব্যবহার হয় না।

```powershell
python examples/node_contract.py
python -m unittest tests.test_node_contract tests.test_rpc -v
```

[নথিপত্র](README.html) · [নোড ইন্টারফেস](EXCHANGE_INTEGRATION.html) · [RPC ও HTTP API](RPC_API.html) · [নোড পরিচালনা](NETWORK_RUNBOOK.html) · [সংস্করণের বিবরণ](RELEASE_NOTES.html)

[বিস্তারিত ইংরেজি নির্দেশিকা](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
