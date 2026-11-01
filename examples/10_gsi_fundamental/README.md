# 基盤地図情報

## 準備と実行

公式サービスから基本項目ファイルをダウンロードし、RhinestoneとGDALのPython bindingsを用意します。
ダウンロードしたメタデータをもとに`example.py`が使う`RHINESTONE_GSI_*`環境変数を設定し、
`python examples/10_gsi_fundamental/example.py`を実行します。

この例は、すでに利用者が取得したファイルだけを受け取ります。国土地理院へのログインを自動化せず、
ファイル名からCRSを推測もしません。
