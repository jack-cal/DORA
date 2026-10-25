# SUMUWW · Провера

SUMUWW PC 0.57.46 · Чвор проверава, чува, прослеђује и даје на увид податке ланца.

## Формат потписа

Необавезни SDK у изворном коду саставља трансакције и проверава достављене потписе без кључева и мреже. То није програм за потписивање нити команда чвора. Ограничење P2WPKH важи за формат примера, а не чвор. Лични новчаник остаје доступан.

## Провера

Инсталирајте зависности и покрените python examples/node_contract.py из изворног кода. Јавни пробни кључеви и привремени regtest проверавају слање, одбијање, потврде, реорганизацију и трајност података. Не користе се права средства, кориснички профили или хардвер за потписивање.

```powershell
python examples/node_contract.py
python -m unittest tests.test_node_contract tests.test_rpc -v
```

[Документација](README.html) · [Интерфејс чвора](EXCHANGE_INTEGRATION.html) · [RPC и HTTP API](RPC_API.html) · [Рад чвора](NETWORK_RUNBOOK.html) · [Напомене о издању](RELEASE_NOTES.html)

[Детаљан енглески приручник](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
