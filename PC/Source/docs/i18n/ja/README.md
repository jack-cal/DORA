# SUMUWW · ドキュメント

SUMUWW PC 0.57.46 · ノードはチェーンデータの検証・保存・伝播・照会を担います。

## 署名形式

任意のソース SDK は鍵やネットワークを使わずに取引を組み立て、受け取った署名を検証します。署名プログラムでもノードのコマンドでもありません。P2WPKH 送金の制限は例の形式に対するもので、ノード全体の制限ではありません。従来の個人用ウォレットは使えます。

## RPC・HTTP API

validateaddress はチェックサムと選択したネットワークを確認します。decoderawtransaction の decoded_only は解析のみを示し、署名の有効性や承認を示しません。OP_RETURN 出力は外部プログラム用データを保存します。 ノードに手数料照会、送信前検証、RBF の置換状態、ブロック順のデータ取得を追加しました。置換取引の検証後にのみ、元の未承認取引を削除します。複数署名とロック出力は分離環境での有効化試験用に実装済みですが、公開ネットワークではまだ有効ではありません。

## 検証

依存関係を導入し、ソースから python examples/node_contract.py を実行します。公開テスト鍵と一時的な regtest で送信・拒否・承認・再編成・データ保存を確認します。実資金、ユーザープロファイル、ハードウェア署名器は使用しません。

```text
network: sumuww (dora)
genesis: 00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97
HRP: sumuww
P2P magic: d052470c
1 SMW = 100000000 yugeon
```

[ノード連携](EXCHANGE_INTEGRATION.html) · [RPC・HTTP API](RPC_API.html) · [ノードの運用](NETWORK_RUNBOOK.html) · [変更履歴](RELEASE_NOTES.html) · [検証](EXCHANGE_EXAMPLES.html)

[英語の詳細資料](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
