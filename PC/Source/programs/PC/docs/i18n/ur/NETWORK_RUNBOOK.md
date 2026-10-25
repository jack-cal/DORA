# SUMUWW · نوڈ چلانا

SUMUWW PC 0.57.46 · نوڈ چین کے ڈیٹا کی تصدیق، حفاظت، ترسیل اور استفسار فراہم کرتا ہے۔

## نیٹ ورک اور پتے

عوامی نیٹ ورک `sumuww` اور اندرونی متبادل نام `dora` ہے۔ نیچے genesis hash جانچیں۔ اصل پتے witness v0 P2WPKH اور سکیڑی ہوئی secp256k1 عوامی کلید کا HASH160 استعمال کرتے ہیں۔ memo یا tag لازمی نہیں۔ غلط نیٹ ورک اور ناقص checksum مسترد کریں۔ HD وصولی/بقایا شاخ اور index لکھیں؛ Bitcoin کا derivation path فرض نہ کریں۔

## توثیق اور حدود

نجی Bearer token کے ساتھ عددی loopback `127.0.0.1:18443` پر RPC واضح طور پر فعال کریں۔ والٹ کھولنا یا دور سے دستخط دستیاب نہیں۔ مقامی خدمت یا تصدیق شدہ tunnel استعمال کریں؛ براؤزر کی Origin/Referer درخواست مسترد ہوتی ہے۔ JSON-RPC میں POST `/rpc`، object/array `params` اور `id` ہیں؛ notification پر HTTP 204 ملتا ہے۔ حدود: body 8004096 بائٹ، header 8192، batch 16، بیک وقت درخواستیں 16، وقت 10 سیکنڈ؛ limit 1–1000، offset 0–1000000۔ کل 28 method اور 11 REST route ہیں۔

## لین دین اور بلاک کی تلاش

`getrawtransaction` فعال چین اور mempool تلاش کرتا ہے، صرف الگ شاخ میں موجود لین دین نہیں۔ ان پٹ پچھلے آؤٹ پٹ بتاتا ہے، ایک منفرد بھیجنے والا پتہ نہیں۔ `getblock` کا `verbose` Boolean ہے؛ محفوظ غیر فعال بلاک میں `active=false` اور `confirmations=-1` ہیں۔ خام لین دین بلاک hash سے اب بھی ملتا ہے۔ `findspendingtransaction` صرف فعال چین کے تصدیق شدہ خرچ تلاش کرتا ہے؛ null دستیابی کا ثبوت نہیں۔ `include_mempool=true` کے ساتھ `gettxout` دیکھیں۔ تنظیم نو میں تصدیقیں اور فعال حالت بدل سکتی ہیں۔

## جانچ

ضروری پیکیج نصب کرکے سورس سے python examples/node_contract.py چلائیں۔ عوامی آزمائشی کلیدیں اور عارضی regtest ارسال، مسترد ہونے، تصدیق، تنظیم نو اور ڈیٹا کی حفاظت جانچتے ہیں۔ حقیقی رقم، صارف پروفائل یا ہارڈویئر دستخط کنندہ استعمال نہیں ہوتا۔

```text
network: sumuww (dora)
genesis: 00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97
HRP: sumuww
P2P magic: d052470c
1 SMW = 100000000 yugeon
```

[دستاویزات](README.html) · [نوڈ انٹرفیس](EXCHANGE_INTEGRATION.html) · [RPC اور HTTP API](RPC_API.html) · [نسخے کی تفصیل](RELEASE_NOTES.html) · [جانچ](EXCHANGE_EXAMPLES.html)

[تفصیلی انگریزی حوالہ](../../../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../../../API_CONTRACT.json) · [vectors.json](../../../../../examples/exchange/vectors.json)
