# Rhinestone

Rhinestoneは、日本の公的・地理空間データを探し、利用可能なResourceへ解決し、既存の専門ライブラリへ渡すPythonライブラリです。

利用者が覚える中心概念は次の4つです。

```text
Catalog -> Provider -> Result -> Resource
```

- `Catalog`: Rhinestoneが知っているProviderの集合
- `Provider`: データを提供する主体・サービス
- `Result`: 検索で見つかった候補
- `Resource`: 実際に利用できる具体的なデータ

## 対象ユーザー

Rhinestoneは、次のような利用者を対象にしています。

- 日本の行政・公的オープンデータをPythonから横断的に探索したい利用者
- GIS・リモートセンシングの研究者
- 公的データを扱うデータエンジニア・データ基盤開発者
- Rasterio、GDAL、pyogrioなどへ渡す前のProvider固有処理を共通化したい利用者

Rhinestoneは、Catalogに構成されたProvider内のデータを検索してResultとして発見し、Resourceへ解決することを担当します。実際のGIS処理やデータ解析は既存の専門ライブラリへ委譲します。

## 対象外のユースケース

RhinestoneはGIS処理ライブラリやワークフローエンジンではありません。次の用途には、そのまま利用できないか、追加の検討が必要です。

- GISの空間演算・形式変換・解析そのもの
- ETLやワークフローの実行基盤
- 外部RuntimeやProvider固有の制約を完全に隠蔽すること
- 0.1.x時点で公開APIの長期固定を前提とする本番システム

対応するProvider、Runtime、形式の範囲は[Compatibility](docs/compatibility.md)を、Runtimeの注入方法は[Configuration](docs/configuration.md)を参照してください。RhinestoneはAlpha版のため、公開APIは今後変更される可能性があります。

## インストール

```console
python -m pip install rhinestone
```

## 基本的な使い方

```python
from rhinestone import configure
from rhinestone.catalogs import BUILTIN

app = configure(catalog=BUILTIN)
results = app.search(text="河川")
resource = app.resolve(results[0])

print(resource.uri)
print(resource.metadata)
```

`BUILTIN`はRhinestoneが提供する組み込みCatalogです。`search()`はCatalogに構成されたProvider内のデータを検索してResultを返し、検索結果は`app.resolve(result)`で直接Resourceへ解決できます。
複数Provider時の整数indexingは構成したProvider順の走査用であり、Providerを横断した関連度rankingではありません。詳細は[Search resultの順序](docs/search.md#結果の順序)を参照してください。

検索を使わず、既知のProviderを選んで構成することもできます。

```python
from rhinestone import Catalog, Provider, configure

catalog = Catalog((
    Provider(
        id="my-stac",
        adapter_type="stac",
        settings={"endpoint": "https://stac.example/api"},
    ),
))
app = configure(catalog=catalog)
```

## RuntimeとCredential

GDAL、Rasterio、pyogrio、RDFLibなどの外部Runtimeは利用者が用意します。API keyやtokenはCredentialとして分離します。

```python
app = configure(
    catalog=BUILTIN,
    dependencies={"rasterio": rasterio},
    credentials={"odpt": lambda: odpt_consumer_key},
)
```

HTTP通信はRhinestoneに組み込まれています。

## 内部アーキテクチャ

利用者が意識する必要のない`Source`、`Config`、`AccessPlan`、`Resolver`、各種Adapter、Registryは内部実装です。内部では責務分離のためにこれらの段階を保持しますが、通常の利用導線には出しません。

RhinestoneはGIS I/O、形式変換、空間演算、データ解析を実装せず、解決済みResourceを既存の専門Runtimeへ渡します。

## ドキュメント

- [Documentation](docs/index.md)
- [Getting started](docs/getting-started.md)
- [Configuration](docs/configuration.md)
- [API reference](docs/api.md)
- [Compatibility](docs/compatibility.md)
- [Runtime guide](docs/runtimes.md)
- [API stability and release policy](docs/release-policy.md)

## 開発環境

```console
uv sync --dev
bash scripts/check.sh
```

MIT Licenseです。
