# Rhinestone documentation

Rhinestoneは、日本の公的・地理空間データを探し、解決し、既存ライブラリへ渡すためのPythonライブラリです。

利用者向けのメンタルモデルは次のとおりです。

```text
Catalog -> Provider -> search -> Result -> resolve -> Resource -> open -> Data
```

## 最初の例

Rasterioを用意し、形式が分かっているGeoTIFFを直接Resourceへ解決します。

```console
python -m pip install rhinestone rasterio
```

```python
import rasterio

from rhinestone import Config, configure

app = configure(dependencies={"rasterio": rasterio})
resource = app.resolve(
    Config(
        source_id="direct",
        settings={
            "uri": "https://raw.githubusercontent.com/rasterio/rasterio/57d9fda6c31c5595ea54262f905b43c5f8419e06/tests/data/RGB.byte.tif",
            "format": "geotiff",
            "media_type": "image/tiff",
        },
    )
)

with resource.open("rasterio") as dataset:
    print(dataset.width, "x", dataset.height)
    print("bands:", dataset.count)
```

この例は外部Providerの検索順や検索結果に依存しません。URIはRasterioの
公開テストデータを不変のcommitに固定しています。`direct`は利用者がURIと形式を
すでに知っている場合の入口です。通常のデータ発見では、[Getting started](getting-started.md)
のようにCatalog内を検索し、Resultを直接Resourceへ解決します。Rasterioは利用者が
所有するRuntimeであり、`configure(dependencies=...)`への明示的な注入が必要です。
詳細は[Runtimeの導入ガイド](runtimes.md)を参照してください。

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
- [外部ライブラリ依存方針](dependency-policy.md)
