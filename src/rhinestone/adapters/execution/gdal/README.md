# GDALの実行アダプター

`GdalAdapter` は選択済み Resource を利用者提供の GDAL runtime へ渡します。

- `name`: `gdal`、優先度: `20`
- 対応形式: Shapefile、GeoTIFF、COG、NetCDF、WMS、GML、CityGML、またはXYZタイル
- 翻訳: ZIP の `/vsizip/` URI、remote ZIP の `/vsicurl/`、encoding の open option、XYZ の GDAL WMS XML
- Runtimeの呼び出し: `OpenEx(uri, open_options=...)`

Resource の再選択、データ解析、形式・CRS 変換は行いません。
