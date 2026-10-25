# SUMUWW Android 0.6.95 · RPC・HTTP API

SUMUWW Android 0.6.95 · ノードはチェーンデータの検証・保存・伝播・照会を担います。

API 仕様は内蔵ノードの機能を説明しています。Android アプリには RPC 設定画面はありません。

## RPC・HTTP API

validateaddress はチェックサムと選択したネットワークを確認します。decoderawtransaction の decoded_only は解析のみを示し、署名の有効性や承認を示しません。OP_RETURN 出力は外部プログラム用データを保存します。 ノードに手数料照会、送信前検証、RBF の置換状態、ブロック順のデータ取得を追加しました。置換取引の検証後にのみ、元の未承認取引を削除します。複数署名とロック出力は分離環境での有効化試験用に実装済みですが、公開ネットワークではまだ有効ではありません。

## 金額と使用可能な出力

`_units` は最小単位の整数、`_smw` は小数点以下8桁の文字列、`_dora` は互換用の別名です。`_sumuww` 金額フィールドはありません。1 SMW = 100000000単位です。`gettxout` に `spendable` はなく、未成熟のコインベース出力も返します。次のブロックで使うには100確認以上必要です。`listunspent` は `spendable` で絞り込みます。`getaddressbalance` のavailable金額は未成熟・保留取引で使用中の資金を除外します。メモリプールの新しい出力は確定資金ではありません。ページ間で先端を確認し、選択した入力を再検証してください。

1 SMW = 100,000,000 yugeon です。自動手数料はローカルの観測値に基づく3段階で、承認時間を保証するものではありません。yugeon/vB で手動入力もできます。送信前に、最終手数料と合計を SMW で確認してください。拒否された取引で残高が減ることはありません。

`1 yugeon = 0.00000001 SMW` · `1 SMW = 100000000 yugeon`

| API / wallet | yugeon / SMW |
|---|---|
| minimum relay | 1 yugeon/vB |
| automatic cap | 0.01 SMW |
| manual cap | 1 SMW |
| manual rate | 1–100000 yugeon/vB |

自動手数料には現在の待機データ量、ブロック容量、取引の優先順位を反映します。過去のブロックの手数料は使いません。待機量が少ないときは最低料率を維持します。プレビューは更新され、最終確認時に手数料が固定されます。観測対象は接続中のローカルノードであり、全ノードではありません。

再起動後も、このノードで記録した取引の置換履歴が残ります。削除された取引は残高に反映されません。

採掘履歴では、各ブロックの新規発行報酬、取引手数料報酬、合計を分けて表示します。自分のウォレットが受け取った額は別に表示します。報酬の一部しか請求されていない場合、内訳を推定しません。ノードは手数料推定を含む28個のRPCメソッドを提供し、署名済み取引を検証・中継します。

## 取引・ブロックの照会

`getrawtransaction` はアクティブチェーンとメモリプールを検索し、孤立分岐だけの取引は検索しません。入力は過去の出力を指し、一意の送信元アドレスを表しません。`getblock` の `verbose` は真偽値です。保存済み非アクティブブロックは `active=false`、`confirmations=-1` となり、生の取引はブロックハッシュで取得できます。`findspendingtransaction` はアクティブチェーンの確定済み使用取引だけを探すため、nullだけで使用可能とは判断できません。`include_mempool=true` の `gettxout` も確認してください。確認数とactive状態は再編で変わり得ます。

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

[API_CONTRACT.json](../../../API_CONTRACT.json)
