# SUMUWW · 查驗

SUMUWW PC 0.57.46 · 節點負責驗證、儲存、傳播與查詢鏈上資料。

## 簽章格式

選用的原始碼 SDK 不需金鑰或網路即可組合交易並驗證傳入的簽章。它不是簽署程式，也不是節點指令。P2WPKH 支付限制只針對範例格式，不針對節點。原有個人錢包仍可使用。

## 查驗

安裝相依套件後，從原始碼執行 python examples/node_contract.py。公開測試金鑰與暫時 regtest 驗證提交、拒絕、確認、鏈重組及資料保存，不使用真實資金、使用者設定檔或硬體簽署器。

```powershell
python examples/node_contract.py
python -m unittest tests.test_node_contract tests.test_rpc -v
```

[文件](README.html) · [節點介面](EXCHANGE_INTEGRATION.html) · [RPC 與 HTTP API](RPC_API.html) · [節點運作](NETWORK_RUNBOOK.html) · [版本說明](RELEASE_NOTES.html)

[英文詳細參考](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
