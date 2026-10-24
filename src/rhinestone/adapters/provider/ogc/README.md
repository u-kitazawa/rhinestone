# OGC API Featuresの提供元アダプター

`OgcFeaturesAdapter` は OGC API Features のcollectionまたはfeatureを `Resource` に変換します。

- Adapter 種別（`adapter_type`）: `ogc-features`
- Provider設定: `endpoint`と検索対象の`collection_id`。
- 直接loadのReference: `parameters`の`collection_id`、または`dataset_identifier`が必須。Providerの検索用設定からは補いません。`feature_id`は任意。
- 検索: `bbox`, `time`, `limit`。構築時に `collection_id` も指定します。
- 注入: `get_json(url, params)`。`credential` に論理名を指定し、`credentials` のRegistryから認証情報を取得します。

collection の公式 `items` link を使用し、endpoint や item URL を推測しません。
検索も配信単位のResourceを返します。Provider Adapterはデータ解析を行わず、
loadで生成する`ogc-api-features`のservice queryを実行する組み込みreaderはありません。
設定・URI解決・認証の詳細は[APIリファレンス](../../../../../docs/api/adapters/ogc-features.md)を参照してください。
設定は [schema.json](schema.json) で補完・構造検証できます。
