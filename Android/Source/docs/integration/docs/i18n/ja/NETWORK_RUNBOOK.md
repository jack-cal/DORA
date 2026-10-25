# SUMUWW Android 0.6.95 · ノードの運用

SUMUWW Android 0.6.95 · ノードはチェーンデータの検証・保存・伝播・照会を担います。

## ネットワークとアドレス

公開ネットワークは `sumuww`、内部の別名は `dora` です。下記のジェネシスハッシュも確認してください。標準アドレスは圧縮secp256k1公開鍵のHASH160を使うwitness v0 P2WPKHです。必須のメモやタグはありません。ネットワーク違いや不正なチェックサムは拒否します。HDアドレスの受取・お釣りの分岐とインデックスを記録し、Bitcoinと同じ導出パスとは考えないでください。

## 取引・ブロックの照会

`getrawtransaction` はアクティブチェーンとメモリプールを検索し、孤立分岐だけの取引は検索しません。入力は過去の出力を指し、一意の送信元アドレスを表しません。`getblock` の `verbose` は真偽値です。保存済み非アクティブブロックは `active=false`、`confirmations=-1` となり、生の取引はブロックハッシュで取得できます。`findspendingtransaction` はアクティブチェーンの確定済み使用取引だけを探すため、nullだけで使用可能とは判断できません。`include_mempool=true` の `gettxout` も確認してください。確認数とactive状態は再編で変わり得ます。

[API_CONTRACT.json](../../../API_CONTRACT.json)
