# GSI Tile Source Adapter

`GsiTileAdapter` は注入された国土地理院タイル仕様を XYZ Resource に変換します。
カタログ定義の読み込みは `rhinestone.catalogs` が担当し、Adapter はカタログの保存場所を知りません。

- `source_type`: `gsi-tile`
- 設定: 注入された定義の `id`、または完全なタイル仕様
- 検索: `text`, `limit`
- 対応: HTTPS、XYZ、EPSG:3857、256 px の PNG/JPEG タイル

未知 ID や URL は推測しません。タイルの実行形式への翻訳は `GdalAdapter` の責務です。
設定は [schema.json](schema.json) で補完・構造検証できます。
