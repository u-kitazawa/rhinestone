# ODPTの駅データ

## 準備と実行

ODPTへ登録し、Rhinestoneをインストールして`ODPT_CONSUMER_KEY`を設定します。
HTTP通信は組み込みtransportを使い、`python examples/12_odpt_station/example.py`で実行します。

consumer keyはリクエストを実行するときだけ取得します。Config、Sourceのメタデータ、出典情報には保存しません。
