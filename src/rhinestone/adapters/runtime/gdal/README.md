# GDALの実行アダプター

`GdalAdapter` は選択済み AccessPlan を利用者提供の GDAL runtime へ渡します。

- `name`: `gdal`、優先度: `20`
- 対応形式: Shapefile、GeoTIFF、COG、NetCDF、WMS、GML、KML、CityGML、またはXYZタイル
- 翻訳: ZIP の `/vsizip/` URI、remote ZIP の `/vsicurl/`、encoding の open option、XYZ の GDAL WMS XML
- Runtimeの呼び出し: `OpenEx(uri, open_options=...)`

Resource の再選択、データ解析、形式・CRS 変換は行いません。

通常のHTTPS URIはそのまま`OpenEx`へ渡すため、部分転送を保証しません。
Range対応を確認した静的HTTPSラスタで`/vsicurl/`を使う例と、Resource/Planの
元URIを保持する境界は[GDALガイド](../../../../../docs/api/adapters/gdal.md)を参照してください。
