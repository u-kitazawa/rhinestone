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

`BUILTIN`はRhinestoneが提供する組み込みCatalogです。検索結果は`app.resolve(result)`で直接Resourceへ解決できます。

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

## 開発環境

```console
uv sync --dev
bash scripts/check.sh
```

MIT Licenseです。
