# SUMUWW · RPC 與 HTTP API

SUMUWW PC 0.57.46 · 節點負責驗證、儲存、傳播與查詢鏈上資料。

## RPC 與 HTTP API

validateaddress 檢查校驗碼與所選網路。decoderawtransaction 的 decoded_only 僅表示解析，不代表簽章有效或交易已確認。OP_RETURN 輸出可儲存供外部程式讀取的資料。 節點新增費用查詢、廣播前檢查、RBF 替換狀態，以及依區塊順序讀取資料紀錄的功能。替換交易通過驗證後，才會移除原有待確認交易。多重簽章與鎖定輸出已實作，供獨立環境進行啟用測試，目前尚未在公開網路啟用。

## 驗證與限制

明確啟用 RPC，使用數字回送位址 `127.0.0.1:18443` 及私有 Bearer token。不提供錢包解鎖或遠端簽章。透過本機服務或已驗證通道連線；拒絕瀏覽器 Origin/Referer 請求。JSON-RPC 使用 POST `/rpc`、物件/陣列 `params` 及 `id`；通知回傳 HTTP 204。限制：本文 8004096 位元組、標頭 8192、批次 16、同時請求 16、期限 10 秒；limit 1–1000、offset 0–1000000。共有 28 個方法及 11 條 REST 路由。

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

| method | params |
|---|---|
| `getblockchaininfo` | `{} / []` |
| `gethtlcinfo` | `{} / []` |
| `getspendinginfo` | `{} / []` |
| `getdatarecords` | `blockhash, offset=0, limit=100` |
| `decodescript` | `hex` |
| `gettxout` | `txid, index, include_mempool=true` |
| `findspendingtransaction` | `txid, index, start_height=0` |
| `getnetworkinfo` | `{} / []` |
| `getblockcount` | `{} / []` |
| `getbestblockhash` | `{} / []` |
| `getblockhash` | `height` |
| `getblock` | `hash, verbose=true` |
| `getrawmempool` | `{} / []` |
| `getmempoolinfo` | `{} / []` |
| `getmempoolpolicy` | `{} / []` |
| `estimatefee` | `vsize=140, mode=normal` |
| `testmempoolaccept` | `hex` |
| `getmempoolentry` | `txid` |
| `gettransactionstatus` | `txid` |
| `getrawtransaction` | `txid, verbose=true` |
| `decoderawtransaction` | `hex` |
| `validateaddress` | `address` |
| `listunspent` | `address, limit=100, offset=0` |
| `getaddressbalance` | `address` |
| `sendrawtransaction` | `hex` |
| `submitblock` | `hex` |
| `getblocktemplate` | `address` |
| `help` | `{} / []` |

| HTTP | URI | JSON |
|---|---|---|
| `GET` | `/api/v1/info` | `—` |
| `GET` | `/api/v1/network` | `—` |
| `GET` | `/api/v1/mempool` | `—` |
| `GET` | `/api/v1/mempool/info` | `—` |
| `GET` | `/api/v1/blocks/{height-or-hash}` | `—` |
| `GET` | `/api/v1/transactions/{txid}` | `—` |
| `GET` | `/api/v1/addresses/{address}/balance` | `—` |
| `GET` | `/api/v1/addresses/{address}/utxos?limit=100&offset=0` | `—` |
| `POST` | `/api/v1/transactions` | `{"hex":"..."}` |
| `POST` | `/api/v1/blocks` | `{"hex":"..."}` |
| `POST` | `/api/v1/mining/template` | `{"address":"..."}` |

[文件](README.html) · [節點介面](EXCHANGE_INTEGRATION.html) · [節點運作](NETWORK_RUNBOOK.html) · [版本說明](RELEASE_NOTES.html) · [查驗](EXCHANGE_EXAMPLES.html)

[英文詳細參考](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
