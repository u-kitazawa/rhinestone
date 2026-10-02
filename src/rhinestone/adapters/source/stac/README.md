# STACの提供元アダプター

`StacAdapter` は STAC API 1.0 の item asset を `Source` に変換します。

- Adapter 種別（`adapter_type`）: `stac`
- 必須設定: `endpoint`, `collection_id`, `item_id`, `asset_key`
- 検索: `bbox`, `time`, `limit`
- 注入: `get_json(url, params)`。`credential` に論理名を指定し、`credentials` のRegistryから認証情報を取得します。

検索結果は data role を持つ asset がちょうど1件であることを要求します。asset URL やフォーマットは推測しません。
設定は [schema.json](schema.json) で補完・構造検証できます。
