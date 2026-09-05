# OGC API Features Source Adapter

`OgcFeaturesAdapter` は OGC API Features の collection または feature を `Source` に変換します。

- `source_type`: `ogc-features`
- 必須設定: `endpoint`, `collection_id`
- 任意設定: `feature_id`
- 検索: `bbox`, `time`, `limit`。構築時に `collection_id` も指定します。
- 注入: `get_json(url, params)`。`api_token` または `api_key` を指定できます。

collection の公式 `items` link を使用し、endpoint や item URL を推測しません。
設定は [schema.json](schema.json) で補完・構造検証できます。
