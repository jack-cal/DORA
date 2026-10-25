# SUMUWW Android 0.6.95 · نوڈ چلانا

SUMUWW Android 0.6.95 · نوڈ چین کے ڈیٹا کی تصدیق، حفاظت، ترسیل اور استفسار فراہم کرتا ہے۔

## نیٹ ورک اور پتے

عوامی نیٹ ورک `sumuww` اور اندرونی متبادل نام `dora` ہے۔ نیچے genesis hash جانچیں۔ اصل پتے witness v0 P2WPKH اور سکیڑی ہوئی secp256k1 عوامی کلید کا HASH160 استعمال کرتے ہیں۔ memo یا tag لازمی نہیں۔ غلط نیٹ ورک اور ناقص checksum مسترد کریں۔ HD وصولی/بقایا شاخ اور index لکھیں؛ Bitcoin کا derivation path فرض نہ کریں۔

## لین دین اور بلاک کی تلاش

`getrawtransaction` فعال چین اور mempool تلاش کرتا ہے، صرف الگ شاخ میں موجود لین دین نہیں۔ ان پٹ پچھلے آؤٹ پٹ بتاتا ہے، ایک منفرد بھیجنے والا پتہ نہیں۔ `getblock` کا `verbose` Boolean ہے؛ محفوظ غیر فعال بلاک میں `active=false` اور `confirmations=-1` ہیں۔ خام لین دین بلاک hash سے اب بھی ملتا ہے۔ `findspendingtransaction` صرف فعال چین کے تصدیق شدہ خرچ تلاش کرتا ہے؛ null دستیابی کا ثبوت نہیں۔ `include_mempool=true` کے ساتھ `gettxout` دیکھیں۔ تنظیم نو میں تصدیقیں اور فعال حالت بدل سکتی ہیں۔

[API_CONTRACT.json](../../../API_CONTRACT.json)
