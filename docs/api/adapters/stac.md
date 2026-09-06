# StacAdapter

`StacAdapter` は STAC API 1.0 の Item asset を解決します。

[Source Adapter 一覧](../source-adapters.md) · source type: `stac`

## 設定と検索

ProviderConfigでは`endpoint`、Configでは`collection_id`、`item_id`、`asset_key`が
必須です。検索には `bbox`、
`time`、`limit` を使えます。

## Endpoint と認証

Item と Search の公式 STAC API endpoint を `get_json(url, params)` で呼びます。
`api_token` または `api_key` をコンストラクタに指定できます。検索結果では data role の
asset がちょうど一件である必要があり、asset URL や format は推測しません。

## 解決して Rasterio で開く例

```python
import rasterio

from rhinestone import Config, ProviderConfig, configure

app = configure(
    providers={
        "imagery": ProviderConfig(
            "stac", {"endpoint": "https://stac.example/api"}
        )
    },
    dependencies={"http-json": lambda: get_json, "rasterio": lambda: rasterio},
)
resource = app.resolve(
    Config("imagery", {
        "collection_id": "collection-id",
        "item_id": "item-id",
        "asset_key": "asset-key",
    })
)
with resource.open("rasterio") as dataset:
    print(dataset.width, dataset.height)
```

値は STAC API が返す collection、Item、asset の識別子を使います。実在 API を使う
環境変数ベースの手順は、リポジトリ checkout の
`examples/06_stac_cog/README.md` を参照してください。
