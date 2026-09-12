# Rhinestone ドキュメント

Rhinestoneは、日本の公的・地理空間データを探し、使えるデータの場所と形式を確定し、既存ライブラリへ渡すためのPythonライブラリです。

基本の使い方は次のとおりです。

```text
Catalog -> Provider -> search -> Result -> resolve -> Resource -> open -> Data
```

## まず動かす

GDALを用意し、組み込みCatalogの検索結果からResourceを解決して開きます。

```console
python -m pip install rhinestone GDAL
```

```python
from osgeo import gdal

from rhinestone import SearchQuery, configure, sources

app = configure(
    sources=(sources.GSI,),
    dependencies={"gdal": gdal},
)
results = app.search(SearchQuery(text="標準地図", limit=1))
result = results[0]
resource = app.resolve(result)

dataset = resource.open("gdal")
print("URI:", resource.uri)
print("raster size:", dataset.RasterXSize, dataset.RasterYSize)
```

この例は、組み込み一覧全体の順序や外部検索結果に依存しません。`sources.GSI`は国土地理院の
静的な地図定義で、`標準地図`という検索語から対象を一つ選びます。GDALは利用者が用意する
外部ライブラリなので、`configure(dependencies=...)`へ明示的に渡します。詳細は[外部ライブラリの導入](runtimes.md)
を参照してください。

## 用語を簡単に説明すると

| 概念 | 役割 |
| --- | --- |
| `Catalog` | 利用可能なProviderの集合 |
| `Provider` | データを提供するサービスや組織 |
| `Result` | 検索で見つかった候補 |
| `Resource` | URIや形式が確定した、利用できるデータ |
| `Runtime` | Resourceを開くために利用者が用意する外部ライブラリ |
| `Credential` | API keyやtokenなどの認証情報 |

`Source`、`Config`、`AccessPlan`、`Resolver`、Adapter、Registryは内部または高度な拡張向けの概念です。最初から覚える必要はありません。詳しくは[用語と概念](concepts.md)を参照してください。

## 次に読む

- [はじめに](getting-started.md)
- [目的別チュートリアル](tutorials/index.md)
- [用語と概念](concepts.md)
- [アプリケーションを構成する](configuration.md)
- [データを検索する](search.md)
- [Resourceを解決して開く](resolve-and-open.md)
- [APIリファレンス](api.md)
- [対応状況](compatibility.md)
- [Runtimeの導入ガイド](runtimes.md)
- [API安定性とリリース運用](release-policy.md)
- [外部ライブラリ依存方針](dependency-policy.md)
