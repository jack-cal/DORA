# SUMUWW · RPC และ HTTP API

SUMUWW PC 0.57.46 · โหนดตรวจสอบ เก็บ ส่งต่อ และให้ค้นข้อมูลเชน

## RPC และ HTTP API

validateaddress ตรวจเช็กซัมและเครือข่ายที่เลือก decoded_only จาก decoderawtransaction หมายถึงอ่านข้อมูลได้เท่านั้น ไม่ได้รับรองลายเซ็นหรือการยืนยัน OP_RETURN เก็บข้อมูลให้โปรแกรมภายนอก โหนดเพิ่มการสอบถามค่าธรรมเนียม การตรวจสอบก่อนส่ง สถานะการแทนที่ RBF และการอ่านข้อมูลตามลำดับบล็อก ระบบตรวจสอบธุรกรรมใหม่ก่อนลบธุรกรรมที่รออยู่ ลายเซ็นหลายชุดและเอาต์พุตแบบล็อกพัฒนาไว้สำหรับทดสอบการเปิดใช้ในระบบแยก ยังไม่เปิดใช้บนเครือข่ายสาธารณะ

## การยืนยันตัวตนและขีดจำกัด

เปิด RPC อย่างชัดเจนที่ loopback ตัวเลข `127.0.0.1:18443` ด้วย Bearer token ส่วนตัว ไม่มีการปลดล็อกกระเป๋าหรือลงนามระยะไกล ใช้บริการในเครื่องหรืออุโมงค์ที่ยืนยันตัวตน คำขอจากเบราว์เซอร์ที่มี Origin/Referer ถูกปฏิเสธ JSON-RPC ใช้ POST `/rpc`, `params` แบบออบเจ็กต์/อาร์เรย์ และ `id`; notification ตอบ HTTP 204 ขีดจำกัด: body 8004096 ไบต์, header 8192, batch 16, คำขอพร้อมกัน 16, เวลา 10 วินาที; limit 1–1000, offset 0–1000000 มี 28 เมธอดและ 11 เส้นทาง REST

## จำนวนเงินและเอาต์พุตที่ใช้ได้

`_units` คือจำนวนเต็มหน่วยย่อยสุด `_smw` คือข้อความทศนิยม 8 หลัก `_dora` คือชื่อเพื่อความเข้ากันได้ ไม่มีฟิลด์จำนวนเงิน `_sumuww` และ 1 SMW = 100000000 หน่วย `gettxout` ไม่มี `spendable` และอาจคืน coinbase ที่ยังไม่ครบกำหนด ต้องมีอย่างน้อย 100 การยืนยันจึงใช้ในบล็อกถัดไปได้ กรอง `listunspent` ด้วย `spendable`; available ใน `getaddressbalance` ตัดเงินที่ยังไม่ครบกำหนดและถูกใช้ในธุรกรรมรอออก เอาต์พุตใหม่ใน mempool ยังไม่ยืนยัน ตรวจยอดสายโซ่ระหว่างหน้าและตรวจอินพุตที่เลือกซ้ำ

1 SMW = 100,000,000 yugeon ค่าธรรมเนียมอัตโนมัติมีสามระดับจากข้อมูลที่โหนดสังเกตได้ และไม่รับประกันเวลายืนยัน คุณสามารถระบุอัตรา yugeon/vB เองได้ โปรดตรวจสอบค่าธรรมเนียมสุดท้ายและยอดรวมเป็น SMW ก่อนส่ง ธุรกรรมที่ถูกปฏิเสธจะไม่หักยอดคงเหลือ

`1 yugeon = 0.00000001 SMW` · `1 SMW = 100000000 yugeon`

| API / wallet | yugeon / SMW |
|---|---|
| minimum relay | 1 yugeon/vB |
| automatic cap | 0.01 SMW |
| manual cap | 1 SMW |
| manual rate | 1–100000 yugeon/vB |

ค่าธรรมเนียมอัตโนมัติคำนวณจากปริมาณข้อมูลที่รอ ความจุของบล็อก และลำดับความสำคัญของธุรกรรม โดยไม่ใช้ค่าธรรมเนียมจากบล็อกเก่า หากคิวสั้นจะใช้อัตราขั้นต่ำ ตัวอย่างจะอัปเดตและค่าธรรมเนียมจะคงที่เมื่อยืนยันขั้นสุดท้าย ข้อมูลเป็นของโหนดในเครื่องที่เชื่อมต่ออยู่ ไม่ใช่ทุกโหนด

ประวัติการแทนที่ธุรกรรมที่โหนดนี้บันทึกไว้จะยังอยู่หลังเปิดกระเป๋าใหม่ ธุรกรรมที่ถูกนำออกไม่กระทบยอดคงเหลือ

ประวัติการขุดแยกเหรียญออกใหม่ ค่าธรรมเนียมธุรกรรม และรางวัลรวมของแต่ละบล็อก โดยแสดงยอดที่กระเป๋าของคุณได้รับแยกต่างหาก หากรับรางวัลเพียงบางส่วน ระบบจะไม่คาดเดาการแบ่งยอดทั้งสองส่วน โหนดมี RPC 28 วิธี รวมการประมาณค่าธรรมเนียม และตรวจสอบพร้อมส่งต่อธุรกรรมที่ลงนามแล้ว

## ค้นหาธุรกรรมและบล็อก

`getrawtransaction` ค้นในสายโซ่ที่ใช้งานและ mempool ไม่ค้นธุรกรรมที่อยู่เฉพาะแขนงกำพร้า อินพุตระบุเอาต์พุตก่อนหน้า ไม่ใช่ที่อยู่ผู้ส่งเดียว `getblock` รับ `verbose` แบบ Boolean บล็อกที่เก็บแต่ไม่ใช้งานมี `active=false`, `confirmations=-1` ยังอ่านธุรกรรมดิบผ่านแฮชบล็อกได้ `findspendingtransaction` ค้นเฉพาะการใช้ที่ยืนยันในสายโซ่ปัจจุบัน null ไม่พิสูจน์ว่าใช้ได้ ตรวจ `gettxout` ด้วย `include_mempool=true` จำนวนยืนยันและสถานะใช้งานอาจเปลี่ยนเมื่อจัดสายโซ่ใหม่

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

[เอกสาร](README.html) · [อินเทอร์เฟซโหนด](EXCHANGE_INTEGRATION.html) · [การใช้งานโหนด](NETWORK_RUNBOOK.html) · [บันทึกเวอร์ชัน](RELEASE_NOTES.html) · [ผลการตรวจสอบ](EXCHANGE_EXAMPLES.html)

[เอกสารอ้างอิงภาษาอังกฤษฉบับละเอียด](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
