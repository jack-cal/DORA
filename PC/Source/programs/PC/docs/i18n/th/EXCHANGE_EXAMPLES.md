# SUMUWW · ผลการตรวจสอบ

SUMUWW PC 0.57.46 · โหนดตรวจสอบ เก็บ ส่งต่อ และให้ค้นข้อมูลเชน

## รูปแบบลายเซ็น

SDK ซอร์สที่เลือกใช้ได้ประกอบธุรกรรมและตรวจลายเซ็นโดยไม่ใช้กุญแจหรือเครือข่าย ไม่ใช่โปรแกรมลงนามหรือคำสั่งโหนด ข้อจำกัด P2WPKH ใช้กับรูปแบบตัวอย่างเท่านั้น ไม่ใช่โหนด กระเป๋าส่วนตัวเดิมยังใช้งานได้

## ผลการตรวจสอบ

ติดตั้งส่วนประกอบที่จำเป็นแล้วรัน python examples/node_contract.py จากซอร์ส กุญแจทดสอบสาธารณะและ regtest ชั่วคราวตรวจการส่ง การปฏิเสธ การยืนยัน การจัดเชนใหม่ และการเก็บข้อมูล โดยไม่ใช้เงินจริง โปรไฟล์ผู้ใช้ หรืออุปกรณ์ลงนาม

```powershell
python examples/node_contract.py
python -m unittest tests.test_node_contract tests.test_rpc -v
```

[เอกสาร](README.html) · [อินเทอร์เฟซโหนด](EXCHANGE_INTEGRATION.html) · [RPC และ HTTP API](RPC_API.html) · [การใช้งานโหนด](NETWORK_RUNBOOK.html) · [บันทึกเวอร์ชัน](RELEASE_NOTES.html)

[เอกสารอ้างอิงภาษาอังกฤษฉบับละเอียด](../../../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../../../API_CONTRACT.json) · [vectors.json](../../../../../examples/exchange/vectors.json)
