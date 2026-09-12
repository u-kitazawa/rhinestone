# Rasterioの実行アダプター

`RasterioAdapter` は選択済み raster Resource を利用者提供の Rasterio runtime へ渡します。

- `name`: `rasterio`、優先度: `15`
- 対応形式: COG、GeoTIFF
- Runtimeの呼び出し: `open(uri)`

URI は選択済み Resource の値をそのまま使用します。ダウンロード、Resource の再選択、形式・CRS 変換は行いません。
