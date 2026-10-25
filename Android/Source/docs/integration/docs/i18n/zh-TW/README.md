# SUMUWW Android 0.6.95 · 文件

SUMUWW Android 0.6.95 · 節點負責驗證、儲存、傳播與查詢鏈上資料。

## 網路與位址

公開網路為 `sumuww`，內部別名為 `dora`。請核對下方創世區塊雜湊。原生位址採用 witness v0 P2WPKH，以及壓縮 secp256k1 公開金鑰的 HASH160。無須強制 memo 或 tag。應拒絕網路錯誤或檢查碼無效的位址。記錄 HD 收款/找零分支及索引，不要假定與 Bitcoin 的衍生路徑相同。

## 金額與可用輸出

`_units` 為最小單位整數，`_smw` 為 8 位小數字串，`_dora` 為相容別名。不存在 `_sumuww` 金額欄位。1 SMW = 100000000 單位。`gettxout` 沒有 `spendable`，可能回傳未成熟 coinbase 輸出。要在下一區塊花費，至少須 100 次確認。依 `spendable` 篩選 `listunspent`；`getaddressbalance` 的 available 金額排除未成熟及已被待處理交易占用的資金。記憶池新輸出不是已確認資金。分頁時檢查鏈頂並重新驗證所選輸入。

1 SMW = 100,000,000 yugeon。自動費用依本機觀測提供慢速、一般與快速選項，但不保證確認時間。也可手動輸入 yugeon/vB 費率。傳送前請核對以 SMW 顯示的最終費用與總額。遭拒絕的交易不會扣減餘額。

`1 yugeon = 0.00000001 SMW` · `1 SMW = 100000000 yugeon`

| API / wallet | yugeon / SMW |
|---|---|
| minimum relay | 1 yugeon/vB |
| automatic cap | 0.01 SMW |
| manual cap | 1 SMW |
| manual rate | 1–100000 yugeon/vB |

自動手續費依目前待處理資料量、區塊容量和交易優先順序計算，不使用歷史區塊的手續費。待處理量較少時維持最低費率。預覽會更新，最終確認時固定手續費。觀測範圍是已連線的本機節點，並非所有節點。

重新啟動錢包後，本節點記錄的交易替換歷史仍會保留。已移除的交易不計入餘額。

挖礦紀錄分別顯示每個區塊的新增發行獎勵、交易手續費獎勵及總獎勵，錢包實際收到的金額另行顯示。若只領取部分獎勵，不會擅自推定兩類獎勵的分配。節點提供 28 個 RPC 方法，包括手續費估算，並驗證及轉發已簽署交易。

## 交易與區塊查詢

`getrawtransaction` 查詢有效鏈及記憶池，不查詢僅存在於孤立分支的交易。輸入指向之前的輸出，並非唯一傳送地址。`getblock` 的 `verbose` 為布林值；已保存的非有效區塊為 `active=false`、`confirmations=-1`，仍可用區塊雜湊取得原始交易。`findspendingtransaction` 僅查有效鏈上已確認的花費，null 不證明可用。還須查詢 `include_mempool=true` 的 `gettxout`。確認數與有效狀態都可能隨重組改變。

[API_CONTRACT.json](../../../API_CONTRACT.json)
