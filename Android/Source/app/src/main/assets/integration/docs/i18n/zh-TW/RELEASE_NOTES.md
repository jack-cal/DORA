# SUMUWW Android 0.6.95 · 版本說明

SUMUWW Android 0.6.95 · 節點負責驗證、儲存、傳播與查詢鏈上資料。

API 規格描述內建節點核心。Android 應用程式沒有 RPC 設定畫面。

## RPC 與 HTTP API

validateaddress 檢查校驗碼與所選網路。decoderawtransaction 的 decoded_only 僅表示解析，不代表簽章有效或交易已確認。OP_RETURN 輸出可儲存供外部程式讀取的資料。 節點新增費用查詢、廣播前檢查、RBF 替換狀態，以及依區塊順序讀取資料紀錄的功能。替換交易通過驗證後，才會移除原有待確認交易。多重簽章與鎖定輸出已實作，供獨立環境進行啟用測試，目前尚未在公開網路啟用。

[API_CONTRACT.json](../../../API_CONTRACT.json)
