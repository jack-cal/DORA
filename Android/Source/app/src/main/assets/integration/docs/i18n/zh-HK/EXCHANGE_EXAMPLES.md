# SUMUWW Android 0.6.95 · 查驗

SUMUWW Android 0.6.95 · 節點負責驗證、儲存、傳播及查詢鏈上資料。

API 規格描述內置節點核心。Android 應用程式沒有 RPC 設定畫面。

## RPC 與 HTTP API

validateaddress 檢查校驗碼及所選網絡。decoderawtransaction 的 decoded_only 只代表解析，不代表簽署有效或交易已確認。OP_RETURN 輸出可保存供外部程式讀取的資料。 節點新增費用查詢、廣播前檢查、RBF 替換狀態，以及按區塊次序讀取數據記錄的功能。替換交易通過驗證後，才會移除原有待確認交易。多重簽署及鎖定輸出已實作，供獨立環境測試啟用，目前尚未在公開網絡啟用。

## 交易與區塊查詢

`getrawtransaction` 查詢有效鏈及記憶池，不查詢僅存在於孤立分支的交易。輸入指向之前的輸出，並非唯一傳送地址。`getblock` 的 `verbose` 為布爾值；已保存的非有效區塊為 `active=false`、`confirmations=-1`，仍可用區塊雜湊取得原始交易。`findspendingtransaction` 僅查有效鏈上已確認的花費，null 不證明可用。還須查詢 `include_mempool=true` 的 `gettxout`。確認數與有效狀態都可能隨重組改變。

[API_CONTRACT.json](../../../API_CONTRACT.json)
