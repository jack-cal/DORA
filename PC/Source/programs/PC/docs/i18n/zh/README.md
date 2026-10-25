# SUMUWW · 文档

SUMUWW PC 0.57.46 · 节点负责验证、保存、传播和查询链上数据。

## 签名格式

可选的源码 SDK 无需密钥或网络即可组装交易并验证传入的签名。它不是签名程序，也不是节点命令。P2WPKH 支付限制仅针对示例格式，不针对节点。原有个人钱包仍可使用。

## RPC 与 HTTP API

validateaddress 检查校验和及所选网络。decoderawtransaction 的 decoded_only 仅表示解析，不代表签名有效或交易已确认。现有 OP_RETURN 输出可保存供外部程序读取的数据。 节点新增费用查询、广播前检查、RBF 替换状态和按区块顺序读取数据记录的功能。只有替换交易通过验证后，才会移除原有待确认交易。多重签名和锁定输出已实现，用于独立环境的激活测试，尚未在公共网络激活。

## 验证

安装依赖后，从源码运行 python examples/node_contract.py。公开测试密钥和临时 regtest 用于验证提交、拒绝、确认、链重组及数据持久性，不使用真实资金、用户配置或硬件签名器。

```text
network: sumuww (dora)
genesis: 00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97
HRP: sumuww
P2P magic: d052470c
1 SMW = 100000000 yugeon
```

[节点接口](EXCHANGE_INTEGRATION.html) · [RPC 与 HTTP API](RPC_API.html) · [节点运行](NETWORK_RUNBOOK.html) · [版本说明](RELEASE_NOTES.html) · [验证](EXCHANGE_EXAMPLES.html)

[英文详细参考](../../../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../../../API_CONTRACT.json) · [vectors.json](../../../../../examples/exchange/vectors.json)
