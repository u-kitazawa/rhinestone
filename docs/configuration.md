# アプリケーションを構成する

Rhinestoneは`configure()`で作成した`app`を入口に使います。利用者はAdapterを組み立てず、利用するSourceと外部runtime・credentialを宣言します。HTTP transportはRhinestoneに組み込まれています。

## 組み込みSource

```python
from rhinestone import configure, sources

app = configure(sources=sources.ALL)
```

`sources.ALL`は特別なsentinelではなく、組み込みexternal Sourceの`SourceDefinition`を並べたtupleです。

個別指定も可能です。

```python
app = configure(
    sources=(sources.GEOSPATIAL_JP, sources.PLATEAU),
)
```

SourceDefinitionは「どこを使うか」を表します。例えば`GEOSPATIAL_JP`はCKAN Adapterを利用し、G空間情報センターのendpointを静的設定として保持します。

Configは「そのSourceの何を使うか」を表します。

```python
from rhinestone import Config

config = Config(
    source_id="geospatial-jp",
    settings={"resource_id": "resource-uuid"},
)
```

endpointはConfigへ入れません。

## custom Source

組み込み定義がない提供元を既存Adapterで利用する高度な用途では`SourceDefinition`を明示できます。

```python
from rhinestone import SourceDefinition, configure

app = configure(
    sources=(
        SourceDefinition(
            id="my-stac",
            adapter_type="stac",
            settings={"endpoint": "https://stac.example/api"},
        ),
    ),
)
```

HTTP metadata取得にも組み込みtransportが使われます。通常のGetting Startedでは組み込み`rhinestone.sources`を優先します。

## runtime dependency

Rhinestoneが実装しない外部runtimeだけをfactoryとして渡します。

```python
app = configure(
    sources=sources.ALL,
    dependencies={
        "rdflib": lambda: rdflib,
        "gdal": lambda: gdal,
        "rasterio": lambda: rasterio,
        "pyogrio": lambda: pyogrio,
    },
)
```

factoryは必要になるまで評価されません。HTTP JSON、HTTP text、JSON serviceの通信runtimeを利用者が登録する必要はありません。

## credential

secretはSourceDefinitionやConfigへ保存せず、logical nameに対応するfactoryとして渡します。

```python
app = configure(
    sources=(sources.ESTAT, sources.ODPT),
    credentials={
        "estat": lambda: os.environ["ESTAT_APP_ID"],
        "odpt": lambda: os.environ["ODPT_CONSUMER_KEY"],
    },
)
```

責務は次のように分離します。

- `SourceDefinition`: 静的な提供元情報
- Source Adapter: 接続・解決方法の知識
- built-in HTTP: metadata・文書・JSON serviceの通信
- dependency: GDAL、Rasterio、RDFLib等の外部実行能力
- credential: secret
- `Config`: 選択したSource内で利用する対象

## Direct

`direct`はexternal SourceではなくCore機能です。`sources.ALL`に含まれず、`configure()`だけでも常時利用できます。

次は[データを検索する](search.md)または[Resourceを解決して開く](resolve-and-open.md)へ進んでください。
