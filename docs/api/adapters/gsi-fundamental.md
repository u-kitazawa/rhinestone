# GsiFundamentalAdapter

`GsiFundamentalAdapter` は、取得済みの基盤地図情報 GML をローカル Resource として
解決します。

[Source Adapter 一覧](../source-adapters.md) · source type: `gsi-fundamental`

## 設定

`dataset="basic"`、`path`、`metadata` が必須です。metadata には `mesh`、
`feature_type`、`schema_version`、`download_spec_version`、`crs`、`source_url` を
指定します。ZIP の場合は `archive="zip"` と安全な相対 `entry_point` を指定します。

ダウンロード、GML 解析、CRS 変換は行いません。

GDAL で開くための metadata を含む例は、リポジトリ checkout の
`examples/10_gsi_fundamental/README.md` にあります。
