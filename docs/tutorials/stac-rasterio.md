# STACで衛星画像を探してRasterioで開く

STAC APIを空間範囲で検索し、検索結果からItemを選び、そのItemが示すdata AssetをRhinestoneで解決してRasterioへ渡します。これはItem / asset selection型の例です。

## 必要なもの

- RhinestoneとPython 3.10以上
- STAC API 1.0のendpoint
- Rasterio
- STAC APIへのnetwork access

```console
python -m pip install rhinestone rasterio
export RHINESTONE_STAC_ENDPOINT="https://your-stac.example"
export RHINESTONE_STAC_RESULT_INDEX="0"
```

STAC endpointは、GET可能な検索API (`/search`)とItem取得APIを提供し、検索結果の各Itemに`roles`が`data`のAssetをちょうど1件含む必要があります。この例は認証なしで到達できるendpointを対象にします。現行の公開構成では、組み込みSource CatalogにSTAC endpointは登録されていないため、`Provider`を明示します。

## 検索してAssetを開く

```python
import os

import rasterio

from rhinestone import Provider, configure

stac = Provider(
    id="my-stac",
    adapter_type="stac",
    settings={"endpoint": os.environ["RHINESTONE_STAC_ENDPOINT"]},
)
app = configure(
    sources=(stac,),
    dependencies={"rasterio": rasterio},
)

results = app.search(
    bbox=(139.0, 35.0, 140.0, 36.0),
    limit=10,
)
if not results:
    raise RuntimeError("STACの検索結果がありません")

for index, result in enumerate(results):
    print(f"[{index}] {result.title}")

selected = results[int(os.environ["RHINESTONE_STAC_RESULT_INDEX"])]
resource = app.resolve(selected)
if resource.format != "cog":
    raise RuntimeError("選択したAssetはRhinestoneが対応するCOGではありません")

with resource.open("rasterio") as dataset:
    print("resource:", resource.uri)
    print("width:", dataset.width)
    print("height:", dataset.height)
    print("crs:", dataset.crs)
```

RhinestoneはItemからdata Assetを選び、Assetのmedia typeに`cloud-optimized`が明示されている場合だけ`cog`としてResourceを作ります。`.tif`というURL末尾だけから形式を推測しません。`resource.open("rasterio")`では、選択済みのURIを利用者所有のRasterioへ渡します。

Rasterioは画像の読み込みを担当します。Rhinestoneは再投影、バンド演算、形式変換、解析を行いません。大きな画像の転送量、クラウドストレージの認証、Assetの利用条件はSTAC提供元と利用者の責務です。

詳細は[STAC Source Adapter](../api/adapters/stac.md)、[Rasterio](../runtimes.md#rasterio)、[対応状況](../compatibility.md)を参照してください。
