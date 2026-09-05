# GSI Tile Source Adapter

`GsiTileAdapter` は国土地理院タイル定義を XYZ Resource に変換します。

- `source_type`: `gsi-tile`
- 設定: 組み込み定義の `id`、または完全なタイル仕様
- 検索: `text`, `limit`
- 対応: HTTPS、XYZ、EPSG:3857、256 px の PNG/JPEG タイル

未知 ID や URL は推測しません。タイルの実行形式への翻訳は `GdalAdapter` の責務です。
設定は [schema.json](schema.json) で補完・構造検証できます。
