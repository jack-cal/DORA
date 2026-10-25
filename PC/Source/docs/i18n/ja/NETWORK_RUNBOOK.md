# SUMUWW · ノードの運用

SUMUWW PC 0.57.46 · ノードはチェーンデータの検証・保存・伝播・照会を担います。

## ネットワークとアドレス

公開ネットワークは `sumuww`、内部の別名は `dora` です。下記のジェネシスハッシュも確認してください。標準アドレスは圧縮secp256k1公開鍵のHASH160を使うwitness v0 P2WPKHです。必須のメモやタグはありません。ネットワーク違いや不正なチェックサムは拒否します。HDアドレスの受取・お釣りの分岐とインデックスを記録し、Bitcoinと同じ導出パスとは考えないでください。

## 認証と制限

RPCは明示的に有効化し、数値ループバック `127.0.0.1:18443` と非公開のBearerトークンを使います。ウォレット解除や遠隔署名は公開しません。ローカルサービスか認証済みトンネルを使用してください。ブラウザーのOrigin/Referer要求は拒否します。JSON-RPCはPOST `/rpc`、オブジェクトまたは配列の `params`、`id` を使い、通知にはHTTP 204を返します。上限は本文8004096バイト、ヘッダー8192バイト、バッチ16、同時要求16、期限10秒。ページのlimitは1–1000、offsetは0–1000000です。メソッド28個とREST経路11個を提供します。

## 取引・ブロックの照会

`getrawtransaction` はアクティブチェーンとメモリプールを検索し、孤立分岐だけの取引は検索しません。入力は過去の出力を指し、一意の送信元アドレスを表しません。`getblock` の `verbose` は真偽値です。保存済み非アクティブブロックは `active=false`、`confirmations=-1` となり、生の取引はブロックハッシュで取得できます。`findspendingtransaction` はアクティブチェーンの確定済み使用取引だけを探すため、nullだけで使用可能とは判断できません。`include_mempool=true` の `gettxout` も確認してください。確認数とactive状態は再編で変わり得ます。

## 検証

依存関係を導入し、ソースから python examples/node_contract.py を実行します。公開テスト鍵と一時的な regtest で送信・拒否・承認・再編成・データ保存を確認します。実資金、ユーザープロファイル、ハードウェア署名器は使用しません。

```text
network: sumuww (dora)
genesis: 00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97
HRP: sumuww
P2P magic: d052470c
1 SMW = 100000000 yugeon
```

[ドキュメント](README.html) · [ノード連携](EXCHANGE_INTEGRATION.html) · [RPC・HTTP API](RPC_API.html) · [変更履歴](RELEASE_NOTES.html) · [検証](EXCHANGE_EXAMPLES.html)

[英語の詳細資料](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
