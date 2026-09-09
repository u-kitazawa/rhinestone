# Rhinestone documentation

Rhinestoneは、日本の公的・地理空間データを探し、解決し、既存ライブラリへ渡すためのPythonライブラリです。

利用者向けのメンタルモデルは次のとおりです。

```text
Catalog -> Provider -> search -> Result -> resolve -> Resource -> open -> Data
```

## 最初の例

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

この例は`BUILTIN`全体のProvider順序や外部検索結果の偶然に依存しません。
`sources.GSI`は組み込みの静的Sourceで、`標準地図`という明示的な検索条件から
`std`のResultを選びます。GDALは利用者が所有するExecution Runtimeであり、
`configure(dependencies=...)`への明示的な注入が必要です。詳細は[Runtimeの導入ガイド](runtimes.md)
を参照してください。

## 主要概念

| 概念 | 役割 |
| --- | --- |
| `Catalog` | 利用可能なProviderの集合 |
| `Provider` | データを提供する主体・サービス |
| `Result` | 検索で見つかった候補 |
| `Resource` | 解決済みの具体的なデータ |
| `Runtime` | Resourceを開くための利用者所有の外部実行環境 |
| `Credential` | API keyやtokenなどのsecret |

`Source`、`Config`、`AccessPlan`、`Resolver`、Adapter、Registryは内部または高度な拡張向けの概念です。詳細は[用語と概念](concepts.md)を参照してください。

## 次に読む

- [Getting started](getting-started.md)
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
