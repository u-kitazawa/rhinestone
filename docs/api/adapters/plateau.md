# PlateauAdapter

`PlateauAdapter` は G 空間情報センターの CKAN catalog から PLATEAU 配布物を解決します。

[Source Adapter 一覧](../source-adapters.md) · source type: `plateau`

## 設定と endpoint

`dataset_id` または `resource_id` のいずれかが必須です。`endpoint`、`format`、
`archive="zip"`、`entry_point` は任意です。endpoint は CKAN Action API として扱い、
`get_json(url, params)` を注入します。検索条件は `text` と `limit` です。

ZIP の `entry_point` は安全な相対パスでなければなりません。候補の選択は Resolver が
行い、市区町村・年度から配布物を推測しません。

CityGML の ZIP member を明示して GDAL で開く例は、リポジトリ checkout の
`examples/09_plateau_citygml/README.md` にあります。
