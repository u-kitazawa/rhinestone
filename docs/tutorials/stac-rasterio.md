# STACの画像assetをRasterioで開く

STACでは、検索で見つけたItemから、providerが `data` として広告しているassetを選びます。
そのassetのmedia typeがCloud-Optimized GeoTIFFを示す場合だけ、Rhinestoneが `cog` Resource
として解決し、Rasterioへ渡せます。

## 準備

```console
python -m pip install rhinestone rasterio
export RHINESTONE_STAC_ENDPOINT="https://your-public-stac.example/api"
export RHINESTONE_STAC_RESULT_INDEX="0"
```

現在の標準 `configure()` 経路では、STAC metadataのHTTP取得は組み込みtransportを使います。
このチュートリアルでは、認証なしで検索とasset取得ができる公開STAC APIを指定してください。
Rasterioの導入は環境のGDAL/PROJとの組み合わせに依存するため、詳細は
[Runtimeの導入ガイド](../runtimes.md)を確認してください。

## 検索、asset選択、Rasterioへの受け渡し

```python
import os
from collections.abc import Mapping
from typing import Any

import rasterio

from rhinestone import SearchQuery, SourceDefinition, configure


def has_cog_data_asset(result: Any) -> bool:
    """Use STAC-advertised roles and media type; never infer from a filename."""
    assets = result.metadata.raw.get("assets", {})
    if not isinstance(assets, Mapping):
        return False
    for asset in assets.values():
        if not isinstance(asset, Mapping):
            continue
        roles = asset.get("roles", [])
        media_type = asset.get("type")
        if (
            isinstance(roles, (list, tuple))
            and "data" in roles
            and isinstance(media_type, str)
            and "cloud-optimized" in media_type
        ):
            return True
    return False


endpoint = os.environ["RHINESTONE_STAC_ENDPOINT"]
app = configure(
    sources=(
        SourceDefinition(
            id="imagery",
            adapter_type="stac",
            settings={"endpoint": endpoint},
        ),
    ),
    dependencies={"rasterio": rasterio},
)

results = app.search(SearchQuery(limit=10))
cog_results = [result for result in results if has_cog_data_asset(result)]
if not cog_results:
    raise RuntimeError("The STAC search returned no COG data asset")

for index, result in enumerate(cog_results):
    print(f"[{index}] {result.title}")
    print("    collection:", result.provenance.dataset_identifier)
    print("    item:", result.provenance.resource_identifier)

selected = cog_results[
    int(os.environ.get("RHINESTONE_STAC_RESULT_INDEX", "0"))
]
resource = app.resolve(selected)

with resource.open("rasterio") as dataset:
    print("resource:", resource.uri)
    print("format:", resource.format)
    print("width x height:", dataset.width, "x", dataset.height)
    print("bands:", dataset.count)
```

検索結果のmetadataから、STACが返した `roles` と `type` だけを使って候補を絞っています。
`.tif` のようなファイル名からCOGであることを推測していません。`app.resolve(selected)`で
Itemを再取得し、asset URLとmedia typeを検証してから、`resource.open("rasterio")`が選択済み
URIをRasterioへ渡します。

## この例の境界

- 必須: ネットワーク接続、公開STAC API、Rasterioとそのnative依存関係
- credential: この標準経路では認証なしの公開STAC APIを使う
- 変更される値: 検索結果、collection / Item ID、asset URL、media type
- Rhinestoneの責務: STAC検索、Itemとassetの選択、COG Resourceへの解決、Rasterioへの委譲
- Rasterioの責務: URIの読み込み、datasetの提供、ウィンドウ読み込みや解析
- 非対応: asset URLの推測、COGでないassetの自動変換、archiveの展開

STAC Adapterの選択条件と非対応形式は[STAC Adapter](../api/adapters/stac.md)と
[対応状況](../compatibility.md)を参照してください。
