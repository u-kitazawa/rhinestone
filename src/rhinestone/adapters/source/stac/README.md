# STAC Source Adapter

`StacAdapter` は STAC API 1.0 の item asset を `Source` に変換します。

- `source_type`: `stac`
- 必須設定: `endpoint`, `collection_id`, `item_id`, `asset_key`
- 検索: `bbox`, `time`, `limit`
- 注入: `get_json(url, params)`。`api_token` または `api_key` を指定できます。

検索結果は data role を持つ asset がちょうど1件であることを要求します。asset URL やフォーマットは推測しません。
