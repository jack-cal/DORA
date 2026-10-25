# SUMUWW Android 0.6.95 · 节点运行

SUMUWW Android 0.6.95 · 节点负责验证、保存、传播和查询链上数据。

## 网络与地址

公开网络为 `sumuww`，内部别名为 `dora`。请核对下方创世区块哈希。原生地址采用 witness v0 P2WPKH，以及压缩 secp256k1 公钥的 HASH160。无需强制 memo 或 tag。应拒绝网络错误或校验和无效的地址。记录 HD 收款/找零分支及索引，不要假定与 Bitcoin 的派生路径相同。

## 交易与区块查询

`getrawtransaction` 查询活跃链及内存池，不查询仅存在于孤立分支的交易。输入指向之前的输出，并非唯一发送地址。`getblock` 的 `verbose` 为布尔值；已保存的非活跃块为 `active=false`、`confirmations=-1`，仍可用区块哈希取得原始交易。`findspendingtransaction` 仅查活跃链上已确认的花费，null 不证明可用。还需查询 `include_mempool=true` 的 `gettxout`。确认数及活跃状态都可能随重组改变。

[API_CONTRACT.json](../../../API_CONTRACT.json)
