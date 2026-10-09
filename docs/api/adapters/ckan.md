# CkanAdapter（CKAN提供元アダプター）

`CkanAdapter` は CKAN Action API の resource を解決します。

[Source Adapter 一覧](../source-adapters.md) · source type: `ckan`

## 設定と検索

`Reference.parameters` は `resource_id` が必須です。endpoint は構成したCKAN Providerから渡されます。組み込み `geospatial-jp` は[G空間専用Adapter](geospatial-jp.md)を使用します。検索では `text`、`format`、`limit` を使えます。`format`は対象Resourceの宣言済み形式をAdapter内で照合します。`limit` は package 数ではなく形式照合後の Resource 数であり、先頭 page に十分な Resource がなければ Action API の `start` で次 page を取得します。`limit=None` は provider の既定 page だけを取得します。HTTP通信にはRhinestoneの組み込みtransportを使用します。

Providerに`spatial_search=True`を設定した場合だけ`bbox`も利用できます。
`ckanext-spatial`対応を確認したサイトで有効化してください。設定例と`area`の投影は
[データを検索する](../../search.md)を参照してください。

配布 URL は API response から取得し、推測しません。
CKANが広告する `format` はExecution Adapterと共有するcanonical名へ小文字で正規化し、
`GeoPackage`と`gpkg`はどちらも `Resource.format="gpkg"` として扱います。Providerの
元表記はResource candidateのattributesとraw metadataに保持します。

## 解決する例

```python
from rhinestone import Catalog, Reference, Provider, configure

app = configure(
    catalog=Catalog(
        (Provider("catalog", "ckan", {"endpoint": "https://catalog.example"}),)
    ),
)
resource = app.load(Reference("catalog", parameters={"resource_id": "resource-uuid"}))
```

`resource-uuid` は CKAN API の resource ID です。dataset page URL や dataset ID ではありません。G 空間情報センターでは `front.geospatial.jp` ではなく Catalog に定義された CKAN endpoint を使います。環境変数を使う完全な実行手順は、リポジトリ checkout の `examples/02_ckan_shapefile/README.md` を参照してください。
