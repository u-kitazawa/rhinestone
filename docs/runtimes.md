# 外部ライブラリ（Runtime）の導入ガイド

Rhinestone Coreは、外部ライブラリをインストール・選択・更新しません。利用者が用途に合うライブラリを用意します。Source Runtimeは`configure(dependencies=...)`へ、Execution Runtimeは`open(..., runtime=...)`へ渡します。

この責務分離により、Runtimeの依存関係、ネイティブライブラリ、ライセンス、更新時期は利用者の環境で管理できます。Rhinestoneが保証するのは、対応表に記載したAdapterが、供給されたRuntimeの公開APIを呼び出すことです。

## まず確認すること

Runtime が必要になる段階は二つあります。

| 種類 | 必要になる段階 | 現在の Runtime |
| --- | --- | --- |
| Source Runtime | Source Adapter の `search()` または `load()` | `rdflib`（DCAT の RDF 解釈） |
| Execution Runtime | 解決済み Resource の `open()` | `gdal`、`rasterio`、`pyogrio` |

Execution Runtimeは構成時に登録しません。DCAT の `rdflib` は Source Runtime のため、DCAT の検索・解決時に必要です。
GDAL、Rasterio、pyogrioではRuntime実体を渡します。`RuntimeFactory`はSource Runtime専用で、
Execution Runtimeとして渡すと`ExecutionAdapterUnavailableError`になります。
`json-service`だけはCore所有のRuntimeを使い、`open("json-service")`に`runtime`を渡しません。

Source Runtimeのbare valueはcallableでもRuntime実体として扱います。遅延factoryを使う場合だけ明示的に
`RuntimeFactory` で包むため、callable façadeやMockを誤って呼び出しません。

```python
import importlib

from rhinestone import configure
from rhinestone.models import RuntimeFactory

app = configure(
    dependencies={"rdflib": RuntimeFactory(lambda: importlib.import_module("rdflib"))}
)
```

factoryは必要になった時に一度だけ評価され、結果はアプリケーション内でcacheされます。
factoryが失敗した場合は `DependencyUnavailableError` になります。

HTTP metadata の取得と JSON service の通信は Rhinestone に組み込まれているため、HTTP callback や `requests` 互換 Runtime の注入は不要です。

## Runtime 別レシピ

以下のインストール例は、Rhinestone の extras ではありません。環境の Python、OS、配布経路に合う方法を選び、native dependency がある場合は各 Runtime の公式手順を優先してください。

### Rasterio

Rasterio は COG と GeoTIFF を `Resource.open("rasterio", runtime=rasterio)` で開くための Execution Runtime です。

```console
python -m pip install rasterio
```

```python
import rasterio

from rhinestone import Reference, configure

app = configure()
resource = app.load(
    Reference(
        "direct",
        parameters={
            "uri": "https://example.invalid/data.tif",
            "format": "geotiff",
            "media_type": "image/tiff",
        },
    )
)
dataset = app.open(resource, "rasterio", runtime=rasterio)
```

上のURIは例示用なので、実在する配信URIに置き換えてください。既知の対象は
`app.load(Reference(...))`で読み込みます。検索から使う場合は、`app.search()`が返した
formatが`cog`または`geotiff`のResourceを選び、そのまま`open()`へ渡せます。
AccessPlanがない検索結果はopen時にReferenceからloadされるため、事前の`app.load()`は必須ではありません。
Rhinestone は URI を `rasterio.open()` へそのまま渡し、archive の展開や形式変換を行いません。
導入時の wheel、GDAL、PROJ などの組み合わせは [Rasterio の installation guide](https://rasterio.readthedocs.io/en/latest/installation.html) を確認してください。
対応形式であっても、Runtimeのdriver・配信先・認証によって開けない場合があります。
実行段階の失敗は`ResourceAccessError`になります。詳細は[Resourceを開く](resolve-and-open.md)を参照してください。

### GDAL

GDAL は Shapefile、GML、CityGML、GeoTIFF、COG、NetCDF、WMS、GSI XYZ tile などを `Resource.open("gdal", runtime=gdal)` で開くための Execution Runtime です。

```console
# 例。native library と Python bindings の組み合わせを環境に合わせる
python -m pip install GDAL
```

```python
from osgeo import gdal

from rhinestone import configure

app = configure()
dataset = app.open(resource, "gdal", runtime=gdal)
```

GDAL の Python bindings は system GDAL のライブラリと開発ヘッダーを必要とする場合があります。`pip install GDAL` だけで導入できない環境では、[GDAL の Python bindings guide](https://gdal.org/en/stable/api/python_bindings.html) や OS / conda-forge の手順に従ってください。Rhinestone は GDAL の導入や `/vsicurl/` の利用可否を解決しません。

### pyogrio

pyogrio は Rhinestone の representation registry で `vector` と明示された Shapefile、
GeoJSON、GeoPackage、FlatGeobuf、GML、KML、CityGML を `Resource.open("pyogrio", runtime=pyogrio)` で
読み込むための Execution Runtime です。現在の Adapter は `pyogrio.read_dataframe()` を
呼び出すため、GeoPandas も実行時に必要です。

```console
python -m pip install pyogrio geopandas
```

```python
import pyogrio

from rhinestone import configure

app = configure()
frame = app.open(resource, "pyogrio", runtime=pyogrio)
```

Rhinestone は URI と Source が確定した `format` / `encoding` だけを使い、URI suffix や
archive 内容から形式・memberを推測しません。明示された ZIP AccessPlan は GDAL VSI URIに
変換するため、ZIP Shapefileも同じ `resource.open("pyogrio", runtime=pyogrio)` で読めます。GeoDataFrame
以外への変換、空間演算は行いません。選択できても環境の pyogrio/GDAL が read driver を持たない場合や
geometry / field type を読めない場合、`open()` は `ResourceAccessError` になります。GDAL
の導入方法や wheel の対応範囲は [pyogrio の installation guide](https://pyogrio.readthedocs.io/en/latest/install.html) を確認してください。

### RDFLib

RDFLib は DCAT の JSON-LD、Turtle、RDF/XML を解釈する Source Runtime です。`Resource.open()` のための Runtime ではありません。

```console
python -m pip install rdflib
```

```python
from rhinestone.catalogs import Catalog
import rdflib

from rhinestone import Provider, configure

app = configure(
    catalog=Catalog(
        (
            Provider(
                id="my-dcat",
                adapter_type="dcat",
                settings={"catalog_uri": "https://example.test/catalog.ttl"},
            ),
        )
    ),
    dependencies={"rdflib": rdflib},
)
results = app.search(text="dataset")
```

DCAT ProviderのRDF解釈には`dependencies={"rdflib": rdflib}`を使います。factory を使う場合は `dependencies={"rdflib": RuntimeFactory(lambda: rdflib)}` と書けます。DCAT を使わない構成では RDFLib は不要です。

## 現在の対象外 Runtime

`pystac-client`、`pystac` は現行の built-in Adapter が要求する Runtime ではありません。STAC は組み込み HTTP Adapterで動作します。これらを Rhinestone の Runtime として追加インストールしても、現行 Adapter の機能は増えません。

## 検証済みバージョン

「検証済み」はパッケージの依存条件ではなく、RhinestoneのAdapterを実際に実行した範囲です。
「手動検証済み」はCIではなく、記載した環境で再現可能な動作確認を手動実行したことを示します。
OS、Python、ネイティブライブラリの組み合わせが変われば、同じパッケージバージョンでも再確認が必要です。

基準日: 2026-09-08

| 外部ライブラリ | バージョン | 役割／必要な段階 | 検証環境 | 状態 |
| --- | --- | --- | --- | --- |
| RDFLib | 7.6.0 | Source／`search`、`load` | Linux x86_64、CPython 3.12.13 | 手動検証済み |
| Rasterio | 1.5.1 | Execution／`open` | Linux x86_64、CPython 3.12.13 | 手動検証済み |
| pyogrio + GeoPandas | 0.13.0 + 1.1.4 | Execution／`open` | Linux x86_64、CPython 3.12.13 | 手動検証済み |
| GDAL | 3.13.3 | Execution／`open` | — | 未検証（検証環境で導入できなかった） |

Rhinestone の通常 CI は `uv.lock` に固定された RDFLib 6.3.2 を Python 3.10〜3.13、`ubuntu-latest` で検証します。これは package metadata の制約や lockfile の再現性を確認するための範囲であり、上表の latest stable を意味しません。

手動検証では、RDFLibでfixtureのDCAT catalogを解釈し、Rasterioで一時GeoTIFFを開き、pyogrio 0.13.0 と GeoPandas 1.1.4 で一時GeoJSONを読み込みました。GDAL 3.13.3は、検証環境に`gdal-config`とsystem GDALの開発ヘッダーがなく、Python bindingsを導入できなかったため、テスト済みとは扱いません。

### Tested と dependency constraint の違い

例えば `pyproject.toml` の開発用制約が `rdflib>=6,<7` であれば、それは開発環境で解決可能な範囲を表します。`rdflib==7.6.0` を手動で実行できたとしても、その結果は制約を自動的に `>=6,<8` へ変更しません。逆に、制約内の全バージョンが tested であることも意味しません。

Runtime の導入方法、責任境界、候補ライブラリの採用判断は[外部ライブラリ依存方針](dependency-policy.md)、Adapter ごとの対応形式は[対応状況](compatibility.md)を参照してください。
