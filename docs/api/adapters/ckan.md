# CkanAdapter

`CkanAdapter` は CKAN Action API の resource を解決します。

[Source Adapter 一覧](../source-adapters.md) · source type: `ckan`

## 設定と検索

`Config.settings` は `resource_id` が必須です。組み込み Source の endpoint は `sources.GEOSPATIAL_JP` の Catalog 定義から渡されます。検索では `text` と `limit` を使えます。HTTP通信にはRhinestoneの組み込みtransportを使用します。

配布 URL は API response から取得し、推測しません。
CKANが広告する `format` はExecution Adapterと共有するcanonical名へ小文字で正規化し、
`GeoPackage`と`gpkg`はどちらも `Resource.format="gpkg"` として扱います。Providerの
元表記はResource candidateのattributesとraw metadataに保持します。

## 解決する例

```python
from rhinestone import Config, configure, sources

app = configure(
    sources=(sources.GEOSPATIAL_JP,),
)
resource = app.resolve(
    Config("geospatial-jp", {"resource_id": "resource-uuid"})
)
```

`resource-uuid` は CKAN API の resource ID です。dataset page URL や dataset ID ではありません。G 空間情報センターでは `front.geospatial.jp` ではなく Catalog に定義された CKAN endpoint を使います。環境変数を使う完全な実行手順は、リポジトリ checkout の `examples/02_ckan_shapefile/README.md` を参照してください。
