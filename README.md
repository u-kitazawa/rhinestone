# Rhinestone

Rhinestoneは、日本の公的・地理空間データを探し、使えるデータの場所と形式を確定し、GDALやRasterioなどの既存ライブラリへ渡すPythonライブラリです。

まずは次の流れだけ覚えれば使い始められます。

```text
configure -> search -> resolve -> open
```

検索結果を選び、開くまでの最小例は[はじめに](docs/getting-started.md)にあります。

## できること

Rhinestoneは、次のような利用者を対象にしています。

- 日本の行政・公的オープンデータをPythonから探したい利用者
- GIS・リモートセンシングの研究者
- 公的データを扱うデータエンジニア・データ基盤開発者
- Rasterio、GDAL、pyogrioなどへ渡す前のProvider固有処理を共通化したい利用者

Rhinestoneは、データ提供元の検索方法や配布形式の違いを吸収し、利用するデータを`Resource`として確定します。実際のGIS処理やデータ解析は既存の専門ライブラリへ委譲します。

## しないこと

RhinestoneはGIS処理ライブラリやワークフローエンジンではありません。次の用途には、そのまま利用できないか、追加の検討が必要です。

- GISの空間演算・形式変換・解析そのもの
- ETLやワークフローの実行基盤
- 外部ライブラリやProvider固有の制約を完全に隠すこと
- 0.1.x時点で公開APIの長期固定を前提とする本番システム

対応する提供元、形式、外部ライブラリは[対応状況](docs/compatibility.md)を参照してください。RhinestoneはAlpha版のため、公開APIは今後変更される可能性があります。

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

`BUILTIN`はRhinestoneが用意する提供元の一覧です。`search()`はその中のデータ候補を返し、検索結果は`app.resolve(result)`で使えるデータ情報へ解決できます。
複数の提供元を使う場合、結果の順番は設定した順番であり、提供元をまたいだ関連度順ではありません。詳細は[検索結果の順序](docs/search.md#結果の順序)を参照してください。

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

## 外部ライブラリと認証情報

GDAL、Rasterio、pyogrio、RDFLibなど、データを開いたり解釈したりする外部ライブラリは利用者が用意します。API keyやtokenは設定値に直接書かず、認証情報として分離します。

```python
app = configure(
    catalog=BUILTIN,
    dependencies={"rasterio": rasterio},
    credentials={"odpt": lambda: odpt_consumer_key},
)
```

HTTP通信はRhinestoneに組み込まれています。

## APIの段階

通常の利用では、トップレベルの`configure`、`Rhinestone`、`Catalog`、`Provider`、`Config`、
`Result`、`SearchResults`、`Resource`、`sources`を使います。`Source`、`AccessPlan`、
`Metadata`、`Provenance`、Runtime、Adapter、Registryなどを扱う拡張コードは、用途別の
サブモジュールからimportします。詳しくは[APIリファレンス](docs/api.md)の
[拡張・Adapter向けAPI](docs/api.md#拡張-adapter向けapi)を参照してください。

RhinestoneはGIS I/O、形式変換、空間演算、データ解析を実装せず、解決済みResourceを既存の専門Runtimeへ渡します。

## 次に読む

- [ドキュメント入口](docs/index.md)
- [はじめに](docs/getting-started.md)
- [アプリケーションを構成する](docs/configuration.md)
- [APIリファレンス](docs/api.md)
- [対応状況](docs/compatibility.md)
- [外部ライブラリの導入](docs/runtimes.md)

## 開発環境

```console
uv sync --dev
bash scripts/check.sh
```

MIT Licenseです。
