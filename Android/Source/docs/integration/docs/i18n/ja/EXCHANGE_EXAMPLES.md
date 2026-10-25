# SUMUWW Android 0.6.95 · 検証

SUMUWW Android 0.6.95 · ノードはチェーンデータの検証・保存・伝播・照会を担います。

API 仕様は内蔵ノードの機能を説明しています。Android アプリには RPC 設定画面はありません。

## RPC・HTTP API

validateaddress はチェックサムと選択したネットワークを確認します。decoderawtransaction の decoded_only は解析のみを示し、署名の有効性や承認を示しません。OP_RETURN 出力は外部プログラム用データを保存します。 ノードに手数料照会、送信前検証、RBF の置換状態、ブロック順のデータ取得を追加しました。置換取引の検証後にのみ、元の未承認取引を削除します。複数署名とロック出力は分離環境での有効化試験用に実装済みですが、公開ネットワークではまだ有効ではありません。

## 取引・ブロックの照会

`getrawtransaction` はアクティブチェーンとメモリプールを検索し、孤立分岐だけの取引は検索しません。入力は過去の出力を指し、一意の送信元アドレスを表しません。`getblock` の `verbose` は真偽値です。保存済み非アクティブブロックは `active=false`、`confirmations=-1` となり、生の取引はブロックハッシュで取得できます。`findspendingtransaction` はアクティブチェーンの確定済み使用取引だけを探すため、nullだけで使用可能とは判断できません。`include_mempool=true` の `gettxout` も確認してください。確認数とactive状態は再編で変わり得ます。

[API_CONTRACT.json](../../../API_CONTRACT.json)
