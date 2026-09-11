# GdalAdapter

`GdalAdapter` は選択済み Resource を利用者提供の GDAL runtime へ渡します。

[Execution Adapter 一覧](../execution-adapters.md) · 選択名: `gdal` · priority: `20`

## 対応と runtime

Shapefile、GeoTIFF、COG、NetCDF、WMS、GML、CityGML、GSI XYZ tile を扱います。
runtime は `OpenEx(uri, open_options=...)` を提供する必要があります。

ZIP は `/vsizip/`、リモート ZIP は `/vsicurl/` URI に変換し、確定済み encoding を
open option として渡します。Resource の再選択、解析、形式・CRS 変換は行いません。

Resource URI、確定済み encoding、XYZ tile の XML を既存の GDAL runtime へ渡します。
Resource の再選択、解析、形式・CRS 変換、driver 固定は行いません。

参考: [GDAL Security considerations](https://gdal.org/en/stable/user/security.html)
