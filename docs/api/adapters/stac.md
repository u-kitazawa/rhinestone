# StacAdapter

`StacAdapter` は STAC API 1.0 の Item asset を解決します。

[Source Adapter 一覧](../source-adapters.md) · source type: `stac`

## 設定と検索

SourceDefinition の `settings` へ `endpoint`、Config へ `collection_id`、`item_id`、`asset_key` を指定します。検索には `bbox`、`time`、`limit` を使えます。

`collection_id` と `item_id` は未エンコードの論理IDとして指定します。RhinestoneはHTTP requestを組み立てる際に各IDを1つのpath segmentとしてpercent-encodeします。既にエンコードされたように見える値も推測で復号しないため、例えば論理IDの`%2F`はrequest pathでは`%252F`になります。Metadataとprovenanceには元の論理IDを保持します。

## Endpoint と認証

Item と Search の公式 STAC API endpoint はRhinestoneの組み込みHTTP transportで呼びます。`api_token` または `api_key` を既存 Adapter の直接利用時に指定できます。検索結果では data role の asset がちょうど一件である必要があり、asset URL や format は推測しません。

## 解決して Rasterio で開く例

```python
import rasterio

from rhinestone import Config, SourceDefinition, configure

app = configure(
    sources=(
        SourceDefinition(
            id="imagery",
            adapter_type="stac",
            settings={"endpoint": "https://stac.example/api"},
        ),
    ),
    dependencies={"rasterio": rasterio},
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

値は STAC API が返す collection、Item、asset の識別子を使います。実在 API を使う環境変数ベースの手順は、リポジトリ checkout の `examples/06_stac_cog/README.md` を参照してください。
