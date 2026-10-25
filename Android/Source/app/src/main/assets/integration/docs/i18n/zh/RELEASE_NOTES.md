# SUMUWW Android 0.6.95 · 版本说明

SUMUWW Android 0.6.95 · 节点负责验证、保存、传播和查询链上数据。

API 规范描述内置节点核心。Android 应用没有 RPC 配置界面。

## RPC 与 HTTP API

validateaddress 检查校验和及所选网络。decoderawtransaction 的 decoded_only 仅表示解析，不代表签名有效或交易已确认。现有 OP_RETURN 输出可保存供外部程序读取的数据。 节点新增费用查询、广播前检查、RBF 替换状态和按区块顺序读取数据记录的功能。只有替换交易通过验证后，才会移除原有待确认交易。多重签名和锁定输出已实现，用于独立环境的激活测试，尚未在公共网络激活。

[API_CONTRACT.json](../../../API_CONTRACT.json)
