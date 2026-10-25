# SUMUWW Android 0.6.95 · 节点接口

SUMUWW Android 0.6.95 · 节点负责验证、保存、传播和查询链上数据。

API 规范描述内置节点核心。Android 应用没有 RPC 配置界面。

## 网络与地址

公开网络为 `sumuww`，内部别名为 `dora`。请核对下方创世区块哈希。原生地址采用 witness v0 P2WPKH，以及压缩 secp256k1 公钥的 HASH160。无需强制 memo 或 tag。应拒绝网络错误或校验和无效的地址。记录 HD 收款/找零分支及索引，不要假定与 Bitcoin 的派生路径相同。

## RPC 与 HTTP API

validateaddress 检查校验和及所选网络。decoderawtransaction 的 decoded_only 仅表示解析，不代表签名有效或交易已确认。现有 OP_RETURN 输出可保存供外部程序读取的数据。 节点新增费用查询、广播前检查、RBF 替换状态和按区块顺序读取数据记录的功能。只有替换交易通过验证后，才会移除原有待确认交易。多重签名和锁定输出已实现，用于独立环境的激活测试，尚未在公共网络激活。

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

[API_CONTRACT.json](../../../API_CONTRACT.json)
