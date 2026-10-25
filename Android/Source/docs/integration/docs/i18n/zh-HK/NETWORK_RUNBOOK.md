# SUMUWW Android 0.6.95 · 節點運作

SUMUWW Android 0.6.95 · 節點負責驗證、儲存、傳播及查詢鏈上資料。

## 網絡與地址

公開網絡為 `sumuww`，內部別名為 `dora`。請核對下方創世區塊雜湊。原生地址採用 witness v0 P2WPKH，以及壓縮 secp256k1 公鑰的 HASH160。無須強制 memo 或 tag。應拒絕網絡錯誤或檢查碼無效的地址。記錄 HD 收款/找零分支及索引，不要假定與 Bitcoin 的衍生路徑相同。

## 交易與區塊查詢

`getrawtransaction` 查詢有效鏈及記憶池，不查詢僅存在於孤立分支的交易。輸入指向之前的輸出，並非唯一傳送地址。`getblock` 的 `verbose` 為布爾值；已保存的非有效區塊為 `active=false`、`confirmations=-1`，仍可用區塊雜湊取得原始交易。`findspendingtransaction` 僅查有效鏈上已確認的花費，null 不證明可用。還須查詢 `include_mempool=true` 的 `gettxout`。確認數與有效狀態都可能隨重組改變。

[API_CONTRACT.json](../../../API_CONTRACT.json)
