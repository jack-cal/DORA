# SUMUWW · 节点运行

SUMUWW PC 0.57.46 · 节点负责验证、保存、传播和查询链上数据。

## 网络与地址

公开网络为 `sumuww`，内部别名为 `dora`。请核对下方创世区块哈希。原生地址采用 witness v0 P2WPKH，以及压缩 secp256k1 公钥的 HASH160。无需强制 memo 或 tag。应拒绝网络错误或校验和无效的地址。记录 HD 收款/找零分支及索引，不要假定与 Bitcoin 的派生路径相同。

## 认证与限制

明确启用 RPC，使用数字回环地址 `127.0.0.1:18443` 及私有 Bearer token。不提供钱包解锁或远程签名。通过本地服务或已认证隧道连接；拒绝浏览器 Origin/Referer 请求。JSON-RPC 使用 POST `/rpc`、对象/数组 `params` 及 `id`；通知返回 HTTP 204。限制：请求体 8004096 字节、头部 8192 字节、批量 16、并发 16、期限 10 秒；limit 1–1000、offset 0–1000000。共有 28 个方法及 11 条 REST 路由。

## 交易与区块查询

`getrawtransaction` 查询活跃链及内存池，不查询仅存在于孤立分支的交易。输入指向之前的输出，并非唯一发送地址。`getblock` 的 `verbose` 为布尔值；已保存的非活跃块为 `active=false`、`confirmations=-1`，仍可用区块哈希取得原始交易。`findspendingtransaction` 仅查活跃链上已确认的花费，null 不证明可用。还需查询 `include_mempool=true` 的 `gettxout`。确认数及活跃状态都可能随重组改变。

## 验证

安装依赖后，从源码运行 python examples/node_contract.py。公开测试密钥和临时 regtest 用于验证提交、拒绝、确认、链重组及数据持久性，不使用真实资金、用户配置或硬件签名器。

```text
network: sumuww (dora)
genesis: 00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97
HRP: sumuww
P2P magic: d052470c
1 SMW = 100000000 yugeon
```

[文档](README.html) · [节点接口](EXCHANGE_INTEGRATION.html) · [RPC 与 HTTP API](RPC_API.html) · [版本说明](RELEASE_NOTES.html) · [验证](EXCHANGE_EXAMPLES.html)

[英文详细参考](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
