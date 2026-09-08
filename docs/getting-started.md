# Getting started

Rhinestoneは、Catalogに構成されたProvider内のデータを検索してResultとして発見し、ResultをResourceへ解決するライブラリです。

## インストール

```console
pip install rhinestone
```

HTTP通信は組み込みです。GDAL、Rasterio、pyogrioなど、データを開くためのRuntimeだけを必要に応じて用意します。

## 組み込みCatalogを使う

```python
from rhinestone import configure
from rhinestone.catalogs import BUILTIN

app = configure(catalog=BUILTIN)
```

## 検索して解決する

`search()`はCatalogに構成されたProviderを検索対象として、その中のデータ候補をResultとして返します。Provider自体を発見するAPIではありません。

```python
results = app.search(text="河川", limit=5)
result = results[0]
resource = app.resolve(result)

print(resource.uri)
print(resource.format)
print(resource.provenance)
```

検索結果の解決にConfigは必要ありません。

## Providerを限定する

```python
from rhinestone import Catalog, configure
from rhinestone.catalogs import BUILTIN

catalog = Catalog(BUILTIN.providers[:2])
app = configure(catalog=catalog)
```

## 既知のURIを直接扱う

既知のURIを扱う高度な用途では、`direct`のConfigを使えます。通常の利用では検索結果から`app.resolve(result)`を使ってください。

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
