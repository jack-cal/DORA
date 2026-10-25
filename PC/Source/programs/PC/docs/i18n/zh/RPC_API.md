# SUMUWW · RPC 与 HTTP API

SUMUWW PC 0.57.46 · 节点负责验证、保存、传播和查询链上数据。

## RPC 与 HTTP API

validateaddress 检查校验和及所选网络。decoderawtransaction 的 decoded_only 仅表示解析，不代表签名有效或交易已确认。现有 OP_RETURN 输出可保存供外部程序读取的数据。 节点新增费用查询、广播前检查、RBF 替换状态和按区块顺序读取数据记录的功能。只有替换交易通过验证后，才会移除原有待确认交易。多重签名和锁定输出已实现，用于独立环境的激活测试，尚未在公共网络激活。

## 认证与限制

明确启用 RPC，使用数字回环地址 `127.0.0.1:18443` 及私有 Bearer token。不提供钱包解锁或远程签名。通过本地服务或已认证隧道连接；拒绝浏览器 Origin/Referer 请求。JSON-RPC 使用 POST `/rpc`、对象/数组 `params` 及 `id`；通知返回 HTTP 204。限制：请求体 8004096 字节、头部 8192 字节、批量 16、并发 16、期限 10 秒；limit 1–1000、offset 0–1000000。共有 28 个方法及 11 条 REST 路由。

## 金额与可用输出

`_units` 为最小单位整数，`_smw` 为 8 位小数的字符串，`_dora` 为兼容别名。不存在 `_sumuww` 金额字段。1 SMW = 100000000 单位。`gettxout` 没有 `spendable` 字段，可能返回未成熟 coinbase 输出。要在下一区块花费，至少需要 100 次确认。按 `spendable` 筛选 `listunspent`；`getaddressbalance` 的 available 金额排除未成熟及已被待处理交易占用的资金。内存池的新输出不是已确认资金。分页时检查链顶并重新验证所选输入。

1 SMW = 100,000,000 yugeon。自动费用根据本地观测提供慢速、普通和快速选项，但不保证确认时间。也可以手动输入 yugeon/vB 费率。发送前请核对以 SMW 显示的最终费用和总额。被拒绝的交易不会扣减余额。

`1 yugeon = 0.00000001 SMW` · `1 SMW = 100000000 yugeon`

| API / wallet | yugeon / SMW |
|---|---|
| minimum relay | 1 yugeon/vB |
| automatic cap | 0.01 SMW |
| manual cap | 1 SMW |
| manual rate | 1–100000 yugeon/vB |

自动手续费依据当前待处理数据量、区块容量和交易优先级计算，不使用历史区块的手续费。待处理量较少时保持最低费率。预览会更新，最终确认时锁定手续费。观测范围是已连接的本地节点，并非所有节点。

重启钱包后，本节点记录的交易替换历史仍会保留。被移除的交易不计入余额。

挖矿记录分别显示每个区块的新增发行奖励、交易手续费奖励和总奖励，钱包实际收到的金额单独显示。若只领取了部分奖励，不会擅自推定两类奖励的分配。节点提供 28 个 RPC 方法，包括手续费估算，并验证和转发已签名交易。

## 交易与区块查询

`getrawtransaction` 查询活跃链及内存池，不查询仅存在于孤立分支的交易。输入指向之前的输出，并非唯一发送地址。`getblock` 的 `verbose` 为布尔值；已保存的非活跃块为 `active=false`、`confirmations=-1`，仍可用区块哈希取得原始交易。`findspendingtransaction` 仅查活跃链上已确认的花费，null 不证明可用。还需查询 `include_mempool=true` 的 `gettxout`。确认数及活跃状态都可能随重组改变。

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

[文档](README.html) · [节点接口](EXCHANGE_INTEGRATION.html) · [节点运行](NETWORK_RUNBOOK.html) · [版本说明](RELEASE_NOTES.html) · [验证](EXCHANGE_EXAMPLES.html)

[英文详细参考](../../../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../../../API_CONTRACT.json) · [vectors.json](../../../../../examples/exchange/vectors.json)
