# OgcFeaturesAdapter

`OgcFeaturesAdapter` は OGC API Features 1.0 の collection または feature を解決します。

[Source Adapter 一覧](../source-adapters.md) · source type: `ogc-features`

## 設定と検索

`collection_id` が必須です。`endpoint` は Config またはコンストラクタで指定し、
`feature_id` は任意です。検索には `bbox`、`time`、`limit` を使えます（コンストラクタで
対象 `collection_id` を指定）。

## Endpoint と認証

collection が返す公式 `items` link を使用します。`get_json(url, params)` を注入し、
`api_token` または `api_key` を指定できます。item URL は推測しません。
