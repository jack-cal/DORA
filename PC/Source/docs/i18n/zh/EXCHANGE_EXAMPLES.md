# SUMUWW · 验证

SUMUWW PC 0.57.46 · 节点负责验证、保存、传播和查询链上数据。

## 签名格式

可选的源码 SDK 无需密钥或网络即可组装交易并验证传入的签名。它不是签名程序，也不是节点命令。P2WPKH 支付限制仅针对示例格式，不针对节点。原有个人钱包仍可使用。

## 验证

安装依赖后，从源码运行 python examples/node_contract.py。公开测试密钥和临时 regtest 用于验证提交、拒绝、确认、链重组及数据持久性，不使用真实资金、用户配置或硬件签名器。

```powershell
python examples/node_contract.py
python -m unittest tests.test_node_contract tests.test_rpc -v
```

[文档](README.html) · [节点接口](EXCHANGE_INTEGRATION.html) · [RPC 与 HTTP API](RPC_API.html) · [节点运行](NETWORK_RUNBOOK.html) · [版本说明](RELEASE_NOTES.html)

[英文详细参考](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
