# GsiTileAdapter

`GsiTileAdapter` は国土地理院のタイル定義を XYZ Resource として解決します。

[Source Adapter 一覧](../source-adapters.md) · source type: `gsi-tile`

## 設定

組み込み定義の `id` を指定するか、HTTPS URL、`scheme="xyz"`、`crs="EPSG:3857"`、
PNG/JPEG、zoom 範囲、`tile_size=256`、attribution を含む完全な定義を指定します。

検索条件は `text` と `limit` です。未知の ID や URL は推測しません。タイルを GDAL
形式へ翻訳するには `GdalAdapter` を使います。

組み込みの標準地図（`id="std"`）を GDAL で開く例は、リポジトリ checkout の
`examples/08_gsi_tile/README.md` にあります。
