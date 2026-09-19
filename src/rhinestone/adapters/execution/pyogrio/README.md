# pyogrioの実行アダプター

`PyogrioAdapter` は選択済み vector Resource を利用者提供の pyogrio runtime へ渡します。

- `name`: `pyogrio`、優先度: `10`
- 対応形式: representation registry で `vector` と明示された Shapefile、GeoJSON、GeoPackage、FlatGeobuf、GML、KML、CityGML
- 翻訳: 確定済み `encoding` を `read_dataframe()` option へ渡します。
- Runtimeの呼び出し: `read_dataframe(uri, **options)`

Resource の再選択、データ解析、形式・CRS 変換は行いません。
URL suffix や archive 内容から形式を推測しません。pyogrio/GDAL 環境に対応 driver がない、
または geometry / field type を読めない場合は `ResourceAccessError` になります。
