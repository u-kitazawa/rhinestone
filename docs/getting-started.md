# Getting started

Rhinestoneは、組み込みSourceを選択し、検索・解決したResourceを既存ライブラリへ渡すためのライブラリです。

## インストール

```console
pip install rhinestone
```

GDAL、Rasterio、pyogrio等はRhinestoneの固定依存ではありません。必要なruntimeだけを利用者側で用意します。

## 組み込みSourceを使う

通常はRhinestoneが知っている組み込みSourceをまとめて有効にします。

```python
from rhinestone import configure, sources

app = configure(
    sources=sources.ALL,
)
```

`sources.ALL`は全built-in external Sourcesを並べたimmutableなtupleです。`direct`はCore機能なので`ALL`には含まれません。

必要なruntimeやcredentialがある場合だけ追加します。

```python
from rhinestone import configure, sources

app = configure(
    sources=sources.ALL,
    dependencies={
        "http-json": lambda: get_json,
        "rasterio": lambda: rasterio,
    },
    credentials={
        "estat": lambda: estat_app_id,
        "odpt": lambda: odpt_consumer_key,
    },
)
```

factoryは遅延評価されます。Sourceを構成しただけではruntimeやsecretを読み込みません。

## Sourceを絞る

必要なSourceだけを選択できます。

```python
from rhinestone import configure, sources

app = configure(
    sources=(
        sources.GEOSPATIAL_JP,
        sources.PLATEAU,
    ),
    dependencies={"http-json": lambda: get_json},
)
```

## 検索からResourceを解決する

```python
from rhinestone import SearchQuery

results = app.search(SearchQuery(text="河川", limit=5))
result = results["geospatial-jp"][0]
resource = app.resolve(result.to_config())
```

検索結果は`source_id`と、そのSource内の対象を識別する`settings`だけをConfigへ引き継ぎます。endpointなどのSource定義はConfigへ複製しません。

## Direct Resource

既知のURIを直接解決する`direct`はSource選択と無関係に常時利用できます。

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
```

次は[アプリケーションを構成する](configuration.md)、[データを検索する](search.md)、[Resourceを解決して開く](resolve-and-open.md)を参照してください。
