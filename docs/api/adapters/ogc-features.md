# OgcFeaturesAdapter（OGC API Featuresアダプター）

`OgcFeaturesAdapter` は OGC API Features 1.0 の collection または feature を解決します。

[Source Adapter 一覧](../source-adapters.md) · source type: `ogc-features`

## 設定と検索

`collection_id` が必須です。Providerの`settings`へ`endpoint`と検索対象の`collection_id`を指定し、Configの`feature_id`は任意です。検索には `bbox`、`time`、`limit` を使えます。

`collection_id` と `feature_id` は未エンコードの論理IDとして指定します。RhinestoneはHTTP requestまたはfeature resource URIを組み立てる際に各IDを1つのpath segmentとしてpercent-encodeします。既にエンコードされたように見える値も推測で復号しないため、例えば論理IDの`%2F`はpathでは`%252F`になります。`.`と`..`だけのIDもpath traversalとして正規化されないようエンコードします。Metadataとprovenanceには元の論理IDを保持します。

## 接続先と認証

collection が返す公式 `items` link を使用し、HTTP通信はRhinestoneの組み込みtransportで行います。`items`の`href`がrelative URI referenceの場合はCollection responseの最終URI（HTTP redirect後を含む）を基準にRFC 3986の規則でabsolute URIへ解決し、その後に明示されたfeature IDを付加します。元の`href`はraw metadataに保持し、解決済みURIをResourceとprovenanceの`original_url`に使用します。認証付きリクエストでは、認証情報が別originへ転送されないようredirectを許可しません。

Adapterを直接構築する内部テストや再利用用途ではtransport callbackや認証headerを注入できますが、標準の`configure()`経路でHTTP callbackを登録する必要はありません。
