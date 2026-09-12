# STACの画像assetをRasterioで開く

STACでは、Itemが複数の `data` assetを持つことがあります。このチュートリアルでは、
利用するcollection、Item、asset keyを明示し、そのassetのmedia typeが
Cloud-Optimized GeoTIFFを示す場合だけ、Rhinestoneが `cog` Resourceとして解決して
Rasterioへ渡します。

## 準備

```console
python -m pip install rhinestone rasterio
export RHINESTONE_STAC_ENDPOINT="https://your-public-stac.example/api"
export RHINESTONE_STAC_COLLECTION_ID="collection-id"
export RHINESTONE_STAC_ITEM_ID="item-id"
export RHINESTONE_STAC_ASSET_KEY="data-asset-key"
```

現在の標準 `configure()` 経路では、STAC metadataのHTTP取得は組み込みtransportを使います。
このチュートリアルでは、認証なしで検索とasset取得ができる公開STAC APIを指定してください。
Rasterioの導入は環境のGDAL/PROJとの組み合わせに依存するため、詳細は
[Runtimeの導入ガイド](../runtimes.md)を確認してください。

collection ID、Item ID、asset keyは、利用するSTAC APIのcatalogやItem metadataで確認します。
asset keyはURLやファイル名から推測せず、Itemの `assets` に実在するkeyを指定してください。

## Itemとassetの選択、Rasterioへの受け渡し

```python
import os

import rasterio

from rhinestone import Config, Provider, configure


endpoint = os.environ["RHINESTONE_STAC_ENDPOINT"]
collection_id = os.environ["RHINESTONE_STAC_COLLECTION_ID"]
item_id = os.environ["RHINESTONE_STAC_ITEM_ID"]
asset_key = os.environ["RHINESTONE_STAC_ASSET_KEY"]
app = configure(
    sources=(
        Provider(
            id="imagery",
            adapter_type="stac",
            settings={"endpoint": endpoint},
        ),
    ),
    dependencies={"rasterio": rasterio},
)
resource = app.resolve(
    Config(
        source_id="imagery",
        settings={
            "collection_id": collection_id,
            "item_id": item_id,
            "asset_key": asset_key,
        },
    )
)

with resource.open("rasterio") as dataset:
    print("resource:", resource.uri)
    print("format:", resource.format)
    print("width x height:", dataset.width, "x", dataset.height)
    print("bands:", dataset.count)
```

`app.resolve()`は指定したItemを取得し、明示したasset keyのURLとmedia typeを検証します。
`.tif` のようなファイル名からCOGであることは推測しません。
`resource.open("rasterio")`は、検証済みの選択済みURIをRasterioへ渡します。

## 検索時の制約

現行の `StacAdapter.search()` は、各Itemで `data` roleのassetがちょうど1件の場合だけ
そのasset keyを含む検索結果を返します。0件または複数件の場合は、assetを推測せず
`ProviderResponseError` を返します。Federated searchではこのProviderだけが
`provider_failure` として診断され、他のProviderの結果は継続して返されます。そのため、
複数の `data` assetを含み得る一般的なendpointでは、「検索後に結果をfilterしてassetを選ぶ」
ことはできません。

そのようなItemを扱う場合は、この例のように利用するItemとasset keyを明示してください。
単一 `data` assetに制約され、かつそのassetがCOG media typeを広告するcollectionでのみ
このRasterioフローへ検索結果をそのまま `app.resolve(result)` で渡せます。単一assetでも
media typeが未指定または非対応の場合、検索結果は返りますが解決時に
`UnsupportedAccessError` となります。

## この例の境界

- 必須: ネットワーク接続、公開STAC API、Rasterioとそのnative依存関係
- credential: この標準経路では認証なしの公開STAC APIを使う
- 変更される値: Item metadata、asset URL、media type
- Rhinestoneの責務: 明示されたItemとassetの検証、COG Resourceへの解決、Rasterioへの委譲
- Rasterioの責務: URIの読み込み、datasetの提供、ウィンドウ読み込みや解析
- 非対応: asset URLの推測、COGでないassetの自動変換、archiveの展開

STAC Adapterの選択条件と非対応形式は[STAC Adapter](../api/adapters/stac.md)と
[対応状況](../compatibility.md)を参照してください。
