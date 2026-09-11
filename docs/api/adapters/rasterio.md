# RasterioAdapter

`RasterioAdapter` は選択済み raster Resource を利用者提供の Rasterio runtime で開きます。

[Execution Adapter 一覧](../execution-adapters.md) · 選択名: `rasterio` · priority: `15`

COG と GeoTIFF に対応します。runtime は `open(uri)` を提供する必要があります。
選択済み URI をそのまま渡し、archive の展開、Resource の再選択、形式・CRS 変換は行いません。

参考: [Rasterio `open()`](https://rasterio.readthedocs.io/en/stable/api/rasterio.html#rasterio.open)
