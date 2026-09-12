# 外部ライブラリ（Runtime）の導入ガイド

Rhinestone Coreは、外部ライブラリをインストール・選択・更新しません。利用者が用途に合うライブラリを用意し、
`configure(dependencies=...)`へ実体または明示的な`RuntimeFactory`として渡します。

この責務分離により、Runtimeの依存関係、ネイティブライブラリ、ライセンス、更新時期は利用者の環境で管理できます。Rhinestoneが保証するのは、対応表に記載したAdapterが、供給されたRuntimeの公開APIを呼び出すことです。

## まず確認すること

Runtime が必要になる段階は二つあります。

| 種類 | 必要になる段階 | 現在の Runtime |
| --- | --- | --- |
| Source Runtime | Source の `search()` または `resolve()` | `rdflib`（DCAT の RDF 解釈） |
| Execution Runtime | 解決済み Resource の `open()` | `gdal`、`rasterio`、`pyogrio` |

`configure()` と `resolve()` は Execution Runtime の `RuntimeFactory` を評価しません。対象の段階までfactoryは呼び出されません。DCAT の `rdflib` は Source Runtime のため、DCAT の検索・解決時に必要です。

bare valueはcallableでもRuntime実体として扱います。遅延factoryを使う場合だけ明示的に
`RuntimeFactory` で包むため、callable façadeやMockを誤って呼び出しません。

```python
import importlib

from rhinestone import RuntimeFactory, configure

app = configure(
    dependencies={
        "rasterio": RuntimeFactory(lambda: importlib.import_module("rasterio"))
    }
)
```

factoryは必要になった時に一度だけ評価され、結果はアプリケーション内でcacheされます。
factoryが失敗した場合は `DependencyUnavailableError` になります。

HTTP metadata の取得と JSON service の通信は Rhinestone に組み込まれているため、HTTP callback や `requests` 互換 Runtime の注入は不要です。

## Runtime 別レシピ

以下のインストール例は、Rhinestone の extras ではありません。環境の Python、OS、配布経路に合う方法を選び、native dependency がある場合は各 Runtime の公式手順を優先してください。

### Rasterio

Rasterio は COG と GeoTIFF を `Resource.open("rasterio")` で開くための Execution Runtime です。

```console
python -m pip install rasterio
```

```python
import rasterio

from rhinestone import configure

app = configure(dependencies={"rasterio": rasterio})
dataset = app.open(resource, "rasterio")
```

`resource` は `app.resolve(result)` などで取得した、format が `cog` または `geotiff` の Resource です。Rhinestone は URI を `rasterio.open()` へそのまま渡し、archive の展開や形式変換を行いません。導入時の wheel、GDAL、PROJ などの組み合わせは [Rasterio の installation guide](https://rasterio.readthedocs.io/en/latest/installation.html) を確認してください。

### GDAL

GDAL は Shapefile、GML、CityGML、GeoTIFF、COG、NetCDF、WMS、GSI XYZ tile などを `Resource.open("gdal")` で開くための Execution Runtime です。

```console
# 例。native library と Python bindings の組み合わせを環境に合わせる
python -m pip install GDAL
```

```python
from osgeo import gdal

from rhinestone import configure

app = configure(dependencies={"gdal": gdal})
dataset = app.open(resource, "gdal")
```

GDAL の Python bindings は system GDAL のライブラリと開発ヘッダーを必要とする場合があります。`pip install GDAL` だけで導入できない環境では、[GDAL の Python bindings guide](https://gdal.org/en/stable/api/python_bindings.html) や OS / conda-forge の手順に従ってください。Rhinestone は GDAL の導入や `/vsicurl/` の利用可否を解決しません。

### pyogrio

pyogrio は Shapefile、GeoJSON、GeoPackage、FlatGeobuf を `Resource.open("pyogrio")` で読み込むための Execution Runtime です。現在の Adapter は `pyogrio.read_dataframe()` を呼び出すため、GeoPandas も実行時に必要です。

```console
python -m pip install pyogrio geopandas
```

```python
import pyogrio

from rhinestone import configure

app = configure(dependencies={"pyogrio": pyogrio})
frame = app.open(resource, "pyogrio")
```

Rhinestone は URI と Source が確定した `encoding` だけを `read_dataframe()` へ渡します。archive URI の組み立て、GeoDataFrame 以外への変換、空間演算は行いません。GDAL の導入方法や wheel の対応範囲は [pyogrio の installation guide](https://pyogrio.readthedocs.io/en/latest/install.html) を確認してください。

### RDFLib

RDFLib は DCAT の JSON-LD、Turtle、RDF/XML を解釈する Source Runtime です。`Resource.open()` のための Runtime ではありません。

```console
python -m pip install rdflib
```

```python
import rdflib

from rhinestone import Provider, configure

app = configure(
    sources=(Provider(
        id="my-dcat",
        adapter_type="dcat",
        settings={"catalog_uri": "https://example.test/catalog.ttl"},
    ),),
    dependencies={"rdflib": rdflib},
)
results = app.search(text="dataset")
```

DCAT Source を直接構成する場合も、`dependencies={"rdflib": rdflib}` を同じように渡します。factory を使う場合は `dependencies={"rdflib": RuntimeFactory(lambda: rdflib)}` と書けます。DCAT を使わない構成では RDFLib は不要です。

## 現在の対象外 Runtime

`pystac-client`、`pystac` は現行の built-in Adapter が要求する Runtime ではありません。STAC は組み込み HTTP Adapterで動作します。これらを Rhinestone の Runtime として追加インストールしても、現行 Adapter の機能は増えません。

## 検証済みバージョン

「検証済み」はパッケージの依存条件ではなく、RhinestoneのAdapterを実際に実行した範囲です。
「手動検証済み」はCIではなく、記載した環境で再現可能な動作確認を手動実行したことを示します。
OS、Python、ネイティブライブラリの組み合わせが変われば、同じパッケージバージョンでも再確認が必要です。

基準日: 2026-09-08

| 外部ライブラリ | バージョン | 役割／必要な段階 | 検証環境 | 状態 |
| --- | --- | --- | --- | --- |
| RDFLib | 7.6.0 | Source／`search`、`resolve` | Linux x86_64、CPython 3.12.13 | 手動検証済み |
| Rasterio | 1.5.1 | Execution／`open` | Linux x86_64、CPython 3.12.13 | 手動検証済み |
| pyogrio + GeoPandas | 0.13.0 + 1.1.4 | Execution／`open` | Linux x86_64、CPython 3.12.13 | 手動検証済み |
| GDAL | 3.13.3 | Execution／`open` | — | 未検証（検証環境で導入できなかった） |

Rhinestone の通常 CI は `uv.lock` に固定された RDFLib 6.3.2 を Python 3.10〜3.13、`ubuntu-latest` で検証します。これは package metadata の制約や lockfile の再現性を確認するための範囲であり、上表の latest stable を意味しません。

手動検証では、RDFLibでfixtureのDCAT catalogを解釈し、Rasterioで一時GeoTIFFを開き、pyogrio 0.13.0 と GeoPandas 1.1.4 で一時GeoJSONを読み込みました。GDAL 3.13.3は、検証環境に`gdal-config`とsystem GDALの開発ヘッダーがなく、Python bindingsを導入できなかったため、テスト済みとは扱いません。

### Tested と dependency constraint の違い

例えば `pyproject.toml` の開発用制約が `rdflib>=6,<7` であれば、それは開発環境で解決可能な範囲を表します。`rdflib==7.6.0` を手動で実行できたとしても、その結果は制約を自動的に `>=6,<8` へ変更しません。逆に、制約内の全バージョンが tested であることも意味しません。

Runtime の導入方法、責任境界、候補ライブラリの採用判断は[外部ライブラリ依存方針](dependency-policy.md)、Adapter ごとの対応形式は[対応状況](compatibility.md)を参照してください。
