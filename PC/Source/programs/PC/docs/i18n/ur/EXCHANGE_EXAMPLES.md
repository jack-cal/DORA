# SUMUWW · جانچ

SUMUWW PC 0.57.46 · نوڈ چین کے ڈیٹا کی تصدیق، حفاظت، ترسیل اور استفسار فراہم کرتا ہے۔

## دستخط کی ساخت

اختیاری سورس SDK کلید یا نیٹ ورک کے بغیر لین دین بناتا اور فراہم کردہ دستخط جانچتا ہے۔ یہ دستخط پروگرام یا نوڈ کمانڈ نہیں ہے۔ P2WPKH کی حد مثال کے فارمیٹ پر ہے، نوڈ پر نہیں۔ موجودہ ذاتی والیٹ دستیاب رہے گا۔

## جانچ

ضروری پیکیج نصب کرکے سورس سے python examples/node_contract.py چلائیں۔ عوامی آزمائشی کلیدیں اور عارضی regtest ارسال، مسترد ہونے، تصدیق، تنظیم نو اور ڈیٹا کی حفاظت جانچتے ہیں۔ حقیقی رقم، صارف پروفائل یا ہارڈویئر دستخط کنندہ استعمال نہیں ہوتا۔

```powershell
python examples/node_contract.py
python -m unittest tests.test_node_contract tests.test_rpc -v
```

[دستاویزات](README.html) · [نوڈ انٹرفیس](EXCHANGE_INTEGRATION.html) · [RPC اور HTTP API](RPC_API.html) · [نوڈ چلانا](NETWORK_RUNBOOK.html) · [نسخے کی تفصیل](RELEASE_NOTES.html)

[تفصیلی انگریزی حوالہ](../../../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../../../API_CONTRACT.json) · [vectors.json](../../../../../examples/exchange/vectors.json)
