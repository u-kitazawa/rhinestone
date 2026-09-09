# Rhinestone documentation

Rhinestoneは、日本の公的・地理空間データを探し、解決し、既存ライブラリへ渡すためのPythonライブラリです。

利用者向けのメンタルモデルは次のとおりです。

```text
Catalog -> Provider -> search -> Result -> resolve -> Resource -> open -> Data
```

## 最初の例

```python
from rhinestone import configure
from rhinestone.catalogs import BUILTIN

app = configure(catalog=BUILTIN)
result = app.search(text="河川")[0]
resource = app.resolve(result)

with resource.open("rasterio") as dataset:
    ...
```

検索結果を直接解決できるため、通常のフローでConfigを組み立てる必要はありません。

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
- [用語と概念](concepts.md)
- [アプリケーションを構成する](configuration.md)
- [データを検索する](search.md)
- [Resourceを解決して開く](resolve-and-open.md)
- [APIリファレンス](api.md)
- [対応状況](compatibility.md)
- [外部ライブラリ依存方針](dependency-policy.md)
