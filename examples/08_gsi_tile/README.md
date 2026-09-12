# 国土地理院タイル

## 準備と実行

RhinestoneとGDALのPython bindingsを用意し、GDALに必要なドライバーが含まれることを確認してから、
`python examples/08_gsi_tile/example.py`を実行します。

Catalogに定義された`std`（標準地図）のXYZタイルを開きます。作成した地図を公開する前に、
返されたResourceの利用条件メタデータを確認してください。
