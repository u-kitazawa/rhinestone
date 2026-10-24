# GdalAdapter（GDAL実行アダプター）

`GdalAdapter` は選択済み AccessPlan を利用者提供の GDAL runtime へ渡します。

[Runtime Adapter 一覧](../runtime-adapters.md) · 選択名: `gdal` · priority: `20`

## 対応形式とRuntime

Shapefile、GeoTIFF、COG、NetCDF、WMS、GML、KML、CityGML、GSI XYZ tile を扱います。
runtime は `OpenEx(uri, open_options=...)` を提供する必要があります。

ZIP は `/vsizip/`、リモート ZIP は `/vsicurl/` URI に変換し、確定済み encoding を
open option として渡します。Resource の再選択、解析、形式・CRS 変換は行いません。

URI、encoding、XYZ tile設定はAccessPlanから取得します。driverは固定しません。
対応形式でもRuntimeのdriverや実データによって開けない場合は`ResourceAccessError`になります。
GDALがデータセットを返さない場合も同じエラーとし、Runtimeの例外は`__cause__`へ保持します。

参考: [GDALのセキュリティに関する注意](https://gdal.org/en/stable/user/security.html)
