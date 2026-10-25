# SUMUWW · Проверка

SUMUWW PC 0.57.46 · Узел проверяет, хранит, передаёт и предоставляет данные цепочки.

## Формат подписи

Необязательный SDK в исходниках собирает транзакции и проверяет переданные подписи без ключей и сети. Это не программа подписи и не команда узла. Ограничение P2WPKH относится к формату примера, а не к узлу. Прежний личный кошелёк доступен.

## Проверка

Установив зависимости, запустите python examples/node_contract.py из исходников. Открытые тестовые ключи и временная regtest проверяют отправку, отказ, подтверждения, реорганизацию и сохранность данных. Реальные средства, профили пользователей и аппаратные устройства подписи не используются.

```powershell
python examples/node_contract.py
python -m unittest tests.test_node_contract tests.test_rpc -v
```

[Документация](README.html) · [Интерфейс узла](EXCHANGE_INTEGRATION.html) · [RPC и HTTP API](RPC_API.html) · [Эксплуатация узла](NETWORK_RUNBOOK.html) · [Примечания к версии](RELEASE_NOTES.html)

[Подробный справочник на английском](../../../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../../../API_CONTRACT.json) · [vectors.json](../../../../../examples/exchange/vectors.json)
