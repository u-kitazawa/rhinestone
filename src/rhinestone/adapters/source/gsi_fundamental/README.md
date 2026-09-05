# GSI Fundamental Source Adapter

`GsiFundamentalAdapter` は利用者が取得済みの基盤地図情報 GML を明示的なローカル Resource として扱います。

- `source_type`: `gsi-fundamental`
- 必須設定: `dataset: basic`, `path`, `metadata`
- `metadata` 必須項目: `mesh`, `feature_type`, `schema_version`, `download_spec_version`, `crs`, `source_url`
- 任意設定: `archive: zip`, `entry_point`

ダウンロード、GML 解析、CRS 変換は行いません。ZIP は安全な相対 `entry_point` を必須とします。
