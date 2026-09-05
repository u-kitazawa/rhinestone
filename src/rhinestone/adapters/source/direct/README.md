# Direct Source Adapter

`DirectAdapter` は利用者が完全に記述した単一 Resource を `Source` に変換します。

- `source_type`: `direct`
- 必須設定: `uri`, `format`
- 任意設定: `media_type`, `metadata`, `archive`, `encoding`, `layer`, `subdataset`

URL、形式、runtime は推測しません。GDAL・Rasterio・pyogrio・HTTP client の設定はここへ渡さず、実行時依存として別途注入します。
設定は [schema.json](schema.json) で補完・構造検証できます。
