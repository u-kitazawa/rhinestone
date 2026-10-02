# OGC API Featuresの提供元アダプター

`OgcFeaturesAdapter` は OGC API Features の collection または feature を `Source` に変換します。

- Adapter 種別（`adapter_type`）: `ogc-features`
- 必須設定: `endpoint`, `collection_id`
- 任意設定: `feature_id`
- 検索: `bbox`, `time`, `limit`。構築時に `collection_id` も指定します。
- 注入: `get_json(url, params)`。`credential` に論理名を指定し、`credentials` のRegistryから認証情報を取得します。

collection の公式 `items` link を使用し、endpoint や item URL を推測しません。
設定は [schema.json](schema.json) で補完・構造検証できます。
