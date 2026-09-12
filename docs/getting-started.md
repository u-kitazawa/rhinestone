# はじめに

Rhinestoneは、データ提供元を検索し、検索結果を使えるデータ情報へ変換するライブラリです。

## 1. インストール

```console
pip install rhinestone
```

HTTP通信は組み込みです。データを開くときだけ、GDAL、Rasterio、pyogrioなど必要な外部ライブラリを用意します。

## 2. 組み込みの提供元を使う

```python
from rhinestone import configure
from rhinestone.catalogs import BUILTIN

app = configure(catalog=BUILTIN)
```

## 3. 検索して解決する

`search()`は、設定した提供元の中にあるデータ候補を返します。提供元そのものを探すAPIではありません。

```python
results = app.search(text="河川", limit=5)
result = results[0]
resource = app.resolve(result)

print(resource.uri)
print(resource.format)
print(resource.provenance)
```

検索結果の解決に`Config`を組み立てる必要はありません。複数の提供元を設定した場合、
`results[0]`は設定順で最初の提供元の先頭結果です。関連度1位を意味しません。詳しくは[データを検索する](search.md)を参照してください。

## 4. 提供元を限定する

```python
from rhinestone import Catalog, configure
from rhinestone.catalogs import BUILTIN

catalog = Catalog(BUILTIN.providers[:2])
app = configure(catalog=catalog)
```

## 5. URIが分かっている場合

URIと形式がすでに分かっている場合は、`direct`の`Config`で直接指定できます。通常は検索結果から
`app.resolve(result)`を使う方が簡単です。

```python
from rhinestone import Config, configure

app = configure()
resource = app.resolve(Config(
    source_id="direct",
    settings={
        "uri": "https://example.invalid/data.geojson",
        "format": "geojson",
        "media_type": "application/geo+json",
    },
))
```

次は[アプリケーションを構成する](configuration.md)、[データを検索する](search.md)、[Resourceを解決して開く](resolve-and-open.md)を参照してください。
