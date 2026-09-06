# Getting started

Rhinestoneを構成し、Resourceを解決して外部ライブラリで開くまでの最短例です。

## インストール

```console
pip install rhinestone
```

GDAL、Rasterio、pyogrio等はRhinestoneの依存ではありません。データを開く場合だけ、
利用するライブラリを別途インストールします。

## Resourceを解決する

`direct` providerは追加構成なしで利用できます。

```python
from rhinestone import Config, configure

app = configure()
resource = app.resolve(
    Config(
        source_id="direct",
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

`Config.source_id`は構成済みproviderを参照します。RhinestoneはURL suffixから形式を
推測しないため、direct resourceではURIとformatを明示します。

## データを開く

実行Adapterを登録する必要はありません。使用を許可するruntimeだけをfactoryとして
渡します。

```python
import rasterio

app = configure(dependencies={"rasterio": lambda: rasterio})
resource = app.resolve(
    Config(
        source_id="direct",
        settings={
            "uri": "https://example.invalid/elevation.tif",
            "format": "geotiff",
            "media_type": "image/tiff",
        },
    )
)

with resource.open() as dataset:
    print(dataset.count)
```

互換性のあるdependencyが複数ある場合もRhinestoneが決定的に選択します。実行環境を
固定したい場合だけ`resource.open(adapter="rasterio")`を指定します。

## providerを追加する

```python
from rhinestone import ProviderConfig

app = configure(
    providers={
        "gspace": ProviderConfig(
            adapter_type="ckan",
            settings={"endpoint": "https://www.geospatial.jp/ckan"},
        ),
    },
    dependencies={"http-json": lambda: get_json},
)
```

利用者が指定するのはprovider設定と外部dependencyです。Source AdapterとExecution
AdapterはRhinestoneが構成します。

## 次のステップ

- provider、HTTP callback、runtime：[アプリケーションを構成する](configuration.md)
- 検索から選択・解決：[データを検索する](search.md)
- Resourceとエラー：[Resourceを解決して開く](resolve-and-open.md)
- 対応provider・format：[対応状況](compatibility.md)
- 完全な実行例：リポジトリの`examples/README.md`

