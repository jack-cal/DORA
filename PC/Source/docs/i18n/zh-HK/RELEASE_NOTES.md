# SUMUWW · 版本說明

SUMUWW PC 0.57.46 · 節點負責驗證、儲存、傳播及查詢鏈上資料。

## 簽署格式

可選的原始碼 SDK 毋須密鑰或網絡即可組合交易並驗證傳入的簽署。它不是簽署程式，也不是節點指令。P2WPKH 付款限制只針對範例格式，並非節點。原有個人錢包仍可使用。

## RPC 與 HTTP API

validateaddress 檢查校驗碼及所選網絡。decoderawtransaction 的 decoded_only 只代表解析，不代表簽署有效或交易已確認。OP_RETURN 輸出可保存供外部程式讀取的資料。 節點新增費用查詢、廣播前檢查、RBF 替換狀態，以及按區塊次序讀取數據記錄的功能。替換交易通過驗證後，才會移除原有待確認交易。多重簽署及鎖定輸出已實作，供獨立環境測試啟用，目前尚未在公開網絡啟用。

## 查驗

安裝相依套件後，從原始碼執行 python examples/node_contract.py。公開測試密鑰及臨時 regtest 驗證提交、拒絕、確認、鏈重組及資料保存，不使用真實資金、用戶設定檔或硬件簽署器。

[文件](README.html) · [節點介面](EXCHANGE_INTEGRATION.html) · [RPC 與 HTTP API](RPC_API.html) · [節點運作](NETWORK_RUNBOOK.html) · [查驗](EXCHANGE_EXAMPLES.html)

[英文詳細參考](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
