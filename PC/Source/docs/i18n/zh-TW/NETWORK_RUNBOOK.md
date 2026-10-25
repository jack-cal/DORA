# SUMUWW · 節點運作

SUMUWW PC 0.57.46 · 節點負責驗證、儲存、傳播與查詢鏈上資料。

## 網路與位址

公開網路為 `sumuww`，內部別名為 `dora`。請核對下方創世區塊雜湊。原生位址採用 witness v0 P2WPKH，以及壓縮 secp256k1 公開金鑰的 HASH160。無須強制 memo 或 tag。應拒絕網路錯誤或檢查碼無效的位址。記錄 HD 收款/找零分支及索引，不要假定與 Bitcoin 的衍生路徑相同。

## 驗證與限制

明確啟用 RPC，使用數字回送位址 `127.0.0.1:18443` 及私有 Bearer token。不提供錢包解鎖或遠端簽章。透過本機服務或已驗證通道連線；拒絕瀏覽器 Origin/Referer 請求。JSON-RPC 使用 POST `/rpc`、物件/陣列 `params` 及 `id`；通知回傳 HTTP 204。限制：本文 8004096 位元組、標頭 8192、批次 16、同時請求 16、期限 10 秒；limit 1–1000、offset 0–1000000。共有 28 個方法及 11 條 REST 路由。

## 交易與區塊查詢

`getrawtransaction` 查詢有效鏈及記憶池，不查詢僅存在於孤立分支的交易。輸入指向之前的輸出，並非唯一傳送地址。`getblock` 的 `verbose` 為布林值；已保存的非有效區塊為 `active=false`、`confirmations=-1`，仍可用區塊雜湊取得原始交易。`findspendingtransaction` 僅查有效鏈上已確認的花費，null 不證明可用。還須查詢 `include_mempool=true` 的 `gettxout`。確認數與有效狀態都可能隨重組改變。

## 查驗

安裝相依套件後，從原始碼執行 python examples/node_contract.py。公開測試金鑰與暫時 regtest 驗證提交、拒絕、確認、鏈重組及資料保存，不使用真實資金、使用者設定檔或硬體簽署器。

```text
network: sumuww (dora)
genesis: 00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97
HRP: sumuww
P2P magic: d052470c
1 SMW = 100000000 yugeon
```

[文件](README.html) · [節點介面](EXCHANGE_INTEGRATION.html) · [RPC 與 HTTP API](RPC_API.html) · [版本說明](RELEASE_NOTES.html) · [查驗](EXCHANGE_EXAMPLES.html)

[英文詳細參考](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
