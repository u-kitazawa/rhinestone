# RasterioAdapter

`RasterioAdapter` は選択済み raster Resource を利用者提供の Rasterio runtime で開きます。

[Execution Adapter 一覧](../execution-adapters.md) · 選択名: `rasterio` · priority: `15`

COG と GeoTIFF に対応します。runtime は `open(uri)` を提供する必要があります。
選択済み URI をそのまま渡し、archive の展開、Resource の再選択、形式・CRS 変換は行いません。

`network_policy="strict"`では、GDAL VSI locatorに埋め込まれたHTTP(S) URLもCatalog由来の
destination policyで認可します。未認可URLと認識できない`/vsi.../`構文は`open()`を
呼ぶ前に拒否します。
