# SUMUWW · Шалгалт

SUMUWW PC 0.57.46 · Зангилаа гинжний өгөгдлийг шалгаж, хадгалж, дамжуулж, лавлах боломж олгоно.

## Гарын үсгийн формат

Эх код дахь нэмэлт SDK нь түлхүүр болон сүлжээ ашиглахгүйгээр гүйлгээ угсарч, өгсөн гарын үсгийг шалгана. Энэ нь гарын үсэг зурах програм эсвэл зангилааны тушаал биш. P2WPKH хязгаар нь жишээний форматад хамаарна. Хувийн хэтэвчийг ашиглаж болно.

## Шалгалт

Хамаарлуудыг суулгаад эх кодоос python examples/node_contract.py ажиллуулна. Нийтэд ил туршилтын түлхүүр, түр regtest ашиглан илгээлт, татгалзалт, баталгаажуулалт, дахин зохион байгуулалт, өгөгдөл хадгалалтыг шалгана. Бодит хөрөнгө, хэрэглэгчийн профайл, гарын үсгийн төхөөрөмж ашиглахгүй.

```powershell
python examples/node_contract.py
python -m unittest tests.test_node_contract tests.test_rpc -v
```

[Баримт бичиг](README.html) · [Зангилааны интерфэйс](EXCHANGE_INTEGRATION.html) · [RPC ба HTTP API](RPC_API.html) · [Зангилааны ажиллагаа](NETWORK_RUNBOOK.html) · [Хувилбарын тэмдэглэл](RELEASE_NOTES.html)

[Англи дэлгэрэнгүй лавлах](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
