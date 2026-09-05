# Getting started

このガイドでは、Rhinestone を構成し、Resource を解決して外部ライブラリで開く
までを扱います。

## インストール

Rhinestone は Python 3.10 以上に対応します。公開パッケージを使う場合は次を実行
します。

```console
pip install rhinestone
```

GDAL、Rasterio、pyogrio は Rhinestone の依存ではありません。データを開く場合は、
使いたいライブラリを利用者の環境へ別途インストールしてください。

リポジトリから試す場合は、開発依存を含めて同期します。

```console
uv sync --dev
```

## Resource を解決する

まず、URI と形式を明示した Direct resource を解決します。この例はネットワーク
アクセスを行いません。

```python
from rhinestone import Config, configure
from rhinestone.adapters import DirectAdapter

app = configure(
    dependencies={},
    source_adapters=(DirectAdapter(),),
    execution_adapters=(),
)

resource = app.resolve(
    Config(
        source_type="direct",
        settings={
            "uri": "https://example.invalid/boundaries.geojson",
            "format": "geojson",
            "media_type": "application/geo+json",
        },
    )
)

print(resource.uri)
print(resource.metadata)
print(resource.provenance)
```

`Config` は「利用したいデータ」の宣言です。HTTP の実装詳細や GDAL の option は
含めません。Rhinestone は URL suffix や応答内容から形式を推測しないため、Direct
resource では `uri` と `format` を指定します。

## データを開く

COG または GeoTIFF を Rasterio で開くには、Rasterio を dependency factory として
渡し、`RasterioAdapter` を登録します。

```python
import rasterio

from rhinestone.adapters.execution import RasterioAdapter

app = configure(
    dependencies={"rasterio": lambda: rasterio},
    source_adapters=(DirectAdapter(),),
    execution_adapters=(RasterioAdapter(),),
)

resource = app.resolve(
    Config(
        source_type="direct",
        settings={
            "uri": "https://example.invalid/elevation.tif",
            "format": "geotiff",
            "media_type": "image/tiff",
        },
    )
)

with resource.open(adapter="rasterio") as dataset:
    print(dataset.count)
```

`resource.open()` を省略指定で呼ぶと、登録済みで互換性のある Execution Adapter
が選ばれます。複数の Adapter を登録して選択を固定したい場合は、例のように
`adapter="rasterio"` を指定します。

## 次のステップ

- 対応する provider と format は[対応状況](compatibility.md)で確認する
- 実際の provider を使う例は[サンプル集](../examples/README.md)から選ぶ
- 型、エラー、Adapter の契約は[API リファレンス](api.md)を参照する
