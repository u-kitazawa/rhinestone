# GDAL Execution Adapter

`GdalAdapter` は選択済み Resource を利用者提供の GDAL runtime へ渡します。

- `name`: `gdal`、優先度: `20`
- 対応形式: Shapefile, GeoTIFF, COG, NetCDF, WMS, GML, CityGML、または XYZ tile
- 翻訳: ZIP の `/vsizip/` URI、remote ZIP の `/vsicurl/`、encoding の open option、XYZ の GDAL WMS XML
- runtime: `OpenEx(uri, open_options=...)`

Resource の再選択、データ解析、形式・CRS 変換は行いません。
