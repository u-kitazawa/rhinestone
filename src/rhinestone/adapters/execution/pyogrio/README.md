# pyogrio Execution Adapter

`PyogrioAdapter` は選択済み vector Resource を利用者提供の pyogrio runtime へ渡します。

- `name`: `pyogrio`、優先度: `10`
- 対応形式: Shapefile, GeoJSON, GeoPackage, FlatGeobuf
- 翻訳: 確定済み `encoding` を `read_dataframe()` option へ渡します。
- runtime: `read_dataframe(uri, **options)`

Resource の再選択、データ解析、形式・CRS 変換は行いません。
