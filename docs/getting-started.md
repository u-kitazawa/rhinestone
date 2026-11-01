# はじめに

Rhinestoneは、データ提供元を検索し、検索結果を使えるデータ情報へ変換するライブラリです。

## 1. インストール

```console
pip install rhinestone
```

HTTP通信は組み込みです。データを開くときだけ、GDAL、Rasterio、pyogrioなど必要な外部ライブラリを用意します。

`develop`のドキュメントは次回リリース候補を説明します。このブランチのAPIを試す場合は
次のようにインストールしてください。PyPIの公開済み版とはAPIが異なる場合があります。

```console
python -m pip install "rhinestone @ git+https://github.com/u-kitazawa/rhinestone.git@develop"
```

環境を固定する場合は`develop`をコミットSHAへ置き換えます。文書の対象は
[API安定性とリリース運用](release-policy.md)の「文書の対象バージョン」を参照してください。

## 2. Resourceを検索する

```python
import rhinestone as rs

results = rs.search(text="河川", limit=5)
resource = results[0]

print(resource.uri)
print(resource.format)
print(resource.provenance)
```

`search()`は、組み込みの提供元にあるデータ候補を返します。提供元そのものを探すAPIではありません。

検索結果の解決に`Reference`を組み立てる必要はありません。複数の提供元を設定した場合、
`results[0]`は設定順で最初の提供元の先頭結果です。関連度1位を意味しません。詳しくは[データを検索する](search.md)を参照してください。

## 3. 提供元を限定する

```python
from rhinestone import ProviderId, search

results = search(text="河川", providers=[ProviderId.GEOSPATIAL_JP], limit=5)
```

## 4. URIが分かっている場合

URIと形式がすでに分かっている場合は、`direct`の`Reference`で直接指定できます。通常は検索したResourceをそのまま`open()`へ渡します。

```python
from rhinestone import Reference, configure

app = configure()
resource = app.load(
    Reference(
        provider_id="direct",
        parameters={
            "uri": "https://example.invalid/data.geojson",
            "format": "geojson",
            "media_type": "application/geo+json",
        },
    )
)
```

## 5. Resourceを開く

GDALを導入した環境では、組み込みの国土地理院タイル定義からResourceを検索して開けます。
GDALの導入方法は[Runtimeの導入ガイド](runtimes.md)を参照してください。

```python
from osgeo import gdal
from rhinestone import ProviderId, search

resource = search(text="標準地図", providers=[ProviderId.GSI], limit=1)[0]
dataset = resource.open("gdal", runtime=gdal)
print("URI:", resource.uri)
print("raster size:", dataset.RasterXSize, dataset.RasterYSize)
```

この例の検索は静的な定義を使い、Providerを限定するため横断検索の結果順に依存しません。
データを開くときはネットワークとGDALのWMS/XYZ対応が必要です。Rasterioはこのタイル形式には対応しません。
任意の検索結果を任意のRuntimeで開けるわけではないため、[対応状況](compatibility.md)も確認してください。

次は[アプリケーションを構成する](configuration.md)、[データを検索する](search.md)、[Resourceを解決して開く](resolve-and-open.md)を参照してください。
