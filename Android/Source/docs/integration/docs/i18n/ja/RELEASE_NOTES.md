# SUMUWW Android 0.6.95 · 変更履歴

SUMUWW Android 0.6.95 · ノードはチェーンデータの検証・保存・伝播・照会を担います。

API 仕様は内蔵ノードの機能を説明しています。Android アプリには RPC 設定画面はありません。

## RPC・HTTP API

validateaddress はチェックサムと選択したネットワークを確認します。decoderawtransaction の decoded_only は解析のみを示し、署名の有効性や承認を示しません。OP_RETURN 出力は外部プログラム用データを保存します。 ノードに手数料照会、送信前検証、RBF の置換状態、ブロック順のデータ取得を追加しました。置換取引の検証後にのみ、元の未承認取引を削除します。複数署名とロック出力は分離環境での有効化試験用に実装済みですが、公開ネットワークではまだ有効ではありません。

[API_CONTRACT.json](../../../API_CONTRACT.json)
