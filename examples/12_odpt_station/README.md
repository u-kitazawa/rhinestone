# ODPTの駅データ

## 準備と実行

ODPTへ登録し、Rhinestoneをインストールして`ODPT_CONSUMER_KEY`を設定します。
`app.open(reference, "json-service")`でCore所有のHTTP transportを使い、
`python examples/12_odpt_station/example.py`で実行します。外部Runtimeの指定は不要です。

consumer keyはリクエストを実行するときだけ取得します。Reference、Resourceのメタデータ、出典情報には保存しません。
