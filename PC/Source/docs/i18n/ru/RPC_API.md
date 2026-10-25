# SUMUWW · RPC и HTTP API

SUMUWW PC 0.57.46 · Узел проверяет, хранит, передаёт и предоставляет данные цепочки.

## RPC и HTTP API

validateaddress проверяет контрольную сумму и выбранную сеть. decoded_only от decoderawtransaction означает только разбор, а не проверку подписи или подтверждение. Выходы OP_RETURN сохраняют данные для внешних программ. Добавлены запрос комиссии, проверка перед отправкой, состояние замены RBF и чтение данных в порядке блоков. Замена проверяется до удаления ожидающих транзакций. Мультиподпись и блокировка выходов реализованы для изолированных испытаний активации; в публичной сети они пока не активированы.

## Аутентификация и ограничения

Явно включите RPC на числовом loopback `127.0.0.1:18443` с закрытым Bearer-токеном. Разблокировка кошелька и удалённое подписание не предоставляются. Используйте локальный сервис или аутентифицированный туннель; браузерные Origin/Referer отклоняются. JSON-RPC использует POST `/rpc`, объект/массив `params` и `id`; уведомления возвращают HTTP 204. Лимиты: тело 8004096 байт, заголовки 8192, пакет 16, параллельные запросы 16, срок 10 секунд; limit 1–1000, offset 0–1000000. Доступны 28 методов и 11 REST-маршрутов.

## Суммы и доступные выходы

`_units` — целые минимальные единицы, `_smw` — строка с 8 знаками после запятой, `_dora` — совместимый псевдоним. Поля суммы `_sumuww` нет. 1 SMW = 100000000 единиц. В `gettxout` нет `spendable`; возможны незрелые coinbase-выходы. Для траты в следующем блоке нужно минимум 100 подтверждений. Фильтруйте `listunspent` по `spendable`; available в `getaddressbalance` исключает незрелые средства и ожидающие траты. Новые выходы mempool не подтверждены. Проверяйте вершину между страницами и заново проверяйте выбранные входы.

1 SMW = 100 000 000 yugeon. Автоматический расчёт предлагает три уровня по локальным наблюдениям, не гарантируя время подтверждения. Ставку в yugeon/vB можно ввести вручную. Перед отправкой проверьте окончательную комиссию и итог в SMW. Отклонённая транзакция не уменьшает баланс.

`1 yugeon = 0.00000001 SMW` · `1 SMW = 100000000 yugeon`

| API / wallet | yugeon / SMW |
|---|---|
| minimum relay | 1 yugeon/vB |
| automatic cap | 0.01 SMW |
| manual cap | 1 SMW |
| manual rate | 1–100000 yugeon/vB |

Автоматическая комиссия учитывает объём ожидающих данных, вместимость блоков и приоритет транзакций. Комиссии прошлых блоков не используются. При небольшой очереди сохраняется минимальная ставка. Предпросмотр обновляется; окончательное подтверждение фиксирует комиссию. Наблюдения относятся к подключённому локальному узлу, а не ко всем узлам.

История замен, зарегистрированных этим узлом, сохраняется после перезапуска кошелька. Удалённые транзакции не влияют на баланс.

История майнинга отдельно показывает новую эмиссию, комиссии и общую награду каждого блока. Сумма, полученная вашим кошельком, указана отдельно. При частичном получении награды её распределение между двумя составляющими не предполагается. Узел предоставляет 28 методов RPC, включая оценку комиссии, проверяет и передаёт подписанные транзакции.

## Поиск транзакций и блоков

`getrawtransaction` ищет в активной цепи и mempool, но не транзакции только в отброшенных ветках. Входы указывают предыдущие выходы, не единственный адрес отправителя. `getblock` принимает логический `verbose`; сохранённые неактивные блоки имеют `active=false`, `confirmations=-1`. Их сырые транзакции доступны по хешу блока. `findspendingtransaction` ищет только подтверждённые активные траты; null не доказывает доступность. Проверьте `gettxout` с `include_mempool=true`. Подтверждения и активность меняются при реорганизации.

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

[Документация](README.html) · [Интерфейс узла](EXCHANGE_INTEGRATION.html) · [Эксплуатация узла](NETWORK_RUNBOOK.html) · [Примечания к версии](RELEASE_NOTES.html) · [Проверка](EXCHANGE_EXAMPLES.html)

[Подробный справочник на английском](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
