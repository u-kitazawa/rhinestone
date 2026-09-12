# 02 — CKANのShapefile配布物

G空間情報センターのCKAN APIから、指定したResourceを解決する通信ありの例です。データセットのページから
Resourceを推測せず、Resource IDを明示します。

## 準備と実行

```console
cd rhinestone
uv sync --dev
export RHINESTONE_CKAN_RESOURCE_ID="the-resource-uuid"
uv run python examples/02_ckan_shapefile/example.py
```

接続先は`rhinestone.sources.GEOSPATIAL_JP`に定義されています。HTTP通信はRhinestoneに組み込まれているため、
この例ではGDALは必要ありません。ZIP形式のShapefile Resourceを選ぶと、アーカイブ情報も確認できます。

実行時に外部APIへ接続するため、提供元の仕様変更やResource削除によって失敗することがあります。
