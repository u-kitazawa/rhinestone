# OgcFeaturesAdapter

`OgcFeaturesAdapter` は OGC API Features 1.0 の collection または feature を解決します。

[Source Adapter 一覧](../source-adapters.md) · source type: `ogc-features`

## 設定と検索

`collection_id` が必須です。SourceDefinitionの`settings`へ`endpoint`と検索対象の`collection_id`を指定し、Configの`feature_id`は任意です。検索には `bbox`、`time`、`limit` を使えます。

`collection_id` と `feature_id` は未エンコードの論理IDとして指定します。RhinestoneはHTTP requestまたはfeature resource URIを組み立てる際に各IDを1つのpath segmentとしてpercent-encodeします。既にエンコードされたように見える値も推測で復号しないため、例えば論理IDの`%2F`はpathでは`%252F`になります。`.`と`..`だけのIDもpath traversalとして正規化されないようエンコードします。Metadataとprovenanceには元の論理IDを保持します。

## Endpoint と認証

collection が返す公式 `items` link を使用し、HTTP通信はRhinestoneの組み込みtransportで行います。item URL は推測しません。

Adapterを直接構築する内部テストや再利用用途ではtransport callbackや認証headerを注入できますが、標準の`configure()`経路でHTTP callbackを登録する必要はありません。
