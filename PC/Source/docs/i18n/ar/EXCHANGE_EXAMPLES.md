# SUMUWW · التحقق

SUMUWW PC 0.57.46 · تتحقق العقدة من بيانات السلسلة وتحفظها وتنشرها وتتيح الاستعلام عنها.

## صيغة التوقيع

تجمع حزمة SDK الاختيارية في المصدر المعاملات وتتحقق من التوقيعات المقدمة دون مفاتيح أو شبكة. ليست برنامج توقيع ولا أمراً للعقدة. يخص قيد P2WPKH صيغة المثال فقط وليس العقدة. تبقى المحفظة الشخصية الحالية متاحة.

## التحقق

شغّل python examples/node_contract.py من المصدر بعد تثبيت الاعتماديات. تختبر مفاتيح منشورة وregtest مؤقت الإرسال والرفض والتأكيدات وإعادة التنظيم وبقاء البيانات. لا تُستخدم أموال حقيقية أو ملفات مستخدمين أو أجهزة توقيع.

```powershell
python examples/node_contract.py
python -m unittest tests.test_node_contract tests.test_rpc -v
```

[الوثائق](README.html) · [واجهة العقدة](EXCHANGE_INTEGRATION.html) · [واجهة RPC وHTTP](RPC_API.html) · [تشغيل العقدة](NETWORK_RUNBOOK.html) · [ملاحظات الإصدار](RELEASE_NOTES.html)

[المرجع الإنجليزي المفصل](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
