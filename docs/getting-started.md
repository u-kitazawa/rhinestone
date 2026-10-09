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
[ドキュメントの位置付け](documentation-status.md)を参照してください。

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

次は[アプリケーションを構成する](configuration.md)、[データを検索する](search.md)、[Resourceを解決して開く](resolve-and-open.md)を参照してください。
