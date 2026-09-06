# CkanAdapter

`CkanAdapter` は CKAN Action API の resource を解決します。

[Source Adapter 一覧](../source-adapters.md) · source type: `ckan`

## 設定と検索

`Config.settings` は `resource_id` が必須です。`endpoint` はProviderConfigに
指定します。検索では `text` と `limit` を使えます。

## Endpoint と認証

`{endpoint}/api/3/action/resource_show` と `package_show` を呼びます。検索では
`package_search` を使います。`http-json` dependencyを注入し、必要なら
`api_token` または `api_key` の一方をProviderConfigへ渡します。

配布 URL は API response から取得し、推測しません。

## 解決する例

```python
from rhinestone import Config, ProviderConfig, configure

endpoint = "https://www.geospatial.jp/ckan"
app = configure(
    providers={"gspace": ProviderConfig("ckan", {"endpoint": endpoint})},
    dependencies={"http-json": lambda: get_json},
)
resource = app.resolve(
    Config("gspace", {"resource_id": "resource-uuid"})
)
```

`resource-uuid` は CKAN API の resource ID です。dataset page URL や dataset ID では
ありません。G 空間情報センターでは `front.geospatial.jp` ではなく上記 CKAN endpoint
を使います。環境変数を使う完全な実行手順は、リポジトリ checkout の
`examples/02_ckan_shapefile/README.md` を参照してください。
