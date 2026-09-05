# PLATEAU Source Adapter

`PlateauAdapter` は G Spatial Information Center の CKAN catalog から PLATEAU 配布物を変換します。

- `source_type`: `plateau`
- 必須設定: `resource_id` または `dataset_id`
- 任意設定: `endpoint`, `format`, `archive: zip`, `entry_point`
- 検索: CKAN の `text`, `limit`
- 注入: `get_json(url, params)`。

すべての distribution を候補として保持し、Resource の選択は Resolver に委ねます。ZIP は安全な相対 `entry_point` を必須とします。
設定は [schema.json](schema.json) で補完・構造検証できます。
