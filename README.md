# Rhinestone

Rhinestoneは、日本の公的・地理空間データを既存OSSから利用するためのKnowledge / Specification Layerです。配信元、API、フォーマット、アクセス方式に関する知識を保持し、検索結果や明示的なConfigを利用可能なResourceへ解決します。

Rhinestone自身はGISデータ処理エンジンを実装しません。GDAL、Rasterio、pyogrio等が読み込み・変換・解析を担い、Rhinestoneはそれらへ渡すURI、オプション、Resource選択を組み立てます。

## インストール

PyPIからインストールできます。

```console
python -m pip install rhinestone
```

RhinestoneのCoreは、HTTP通信やGISデータ処理ライブラリを直接固定依存しません。必要なruntime dependencyは利用者側で用意し、callback/factoryとして注入します。
## 基本的な使い方

Rhinestoneが知っている組み込みSourceを選択します。

```python
from rhinestone import configure, sources

app = configure(
    sources=sources.ALL,
    dependencies={
        "http-json": lambda: get_json,
        "rasterio": lambda: rasterio,
    },
    credentials={
        "estat": lambda: estat_app_id,
        "odpt": lambda: odpt_consumer_key,
    },
)
```

必要なSourceだけを選択することもできます。

```python
app = configure(
    sources=(sources.GEOSPATIAL_JP, sources.PLATEAU),
)
```

`sources.ALL`はbuilt-in external Sourcesを並べただけのimmutableなtupleです。`direct`はCore機能なので`ALL`には含まれず、常時利用できます。

検索からResourceまでは同じ流れで接続します。

```python
from rhinestone import SearchQuery

results = app.search(SearchQuery(text="河川", limit=5))
result = results["geospatial-jp"][0]
resource = app.resolve(result.to_config())
```

## 設計上の境界

- `SourceDefinition`: どのデータ提供元を使うか
- `Config`: そのSource内で何を使うか
- Source Adapter: 接続・解決方法の知識
- dependency: HTTP、GDAL、Rasterio、SDK等のruntime
- credential: secret

SourceのendpointはSourceDefinition側に属し、検索結果やConfigへ複製しません。secretやruntime dependencyもSourceDefinitionへ保存しません。

## アーキテクチャ

```text
SourceDefinition[] + dependencies + credentials
  -> configure()
  -> Application

SearchQuery
  -> [Search Coordinator]
  -> [Source Adapter]...
  -> SearchResult[]
  -> Config
  -> [Source Adapter]
  -> Source
  -> [Resolver]
  -> AccessPlan
  -> Resource
  -> [Execution Adapter]
  -> user-provided dependency
```

## 設計原則

- データそのものではなく、データへのアクセス方法を統一する。
- 利用者にAdapterやendpointの組み立てを要求せず、既知のSourceを選択させる。
- 配信元固有の知識はSource Adapterに閉じ込める。
- 解決済みMetadataとProvenanceをResourceまで保持する。
- 実行時依存は利用者が所有し、callback/factoryとして供給する。
- secretはcredential factoryとして分離する。
- 公式の機械可読インターフェースを使い、CoreではHTML scrapingを行わない。
- 確実に判断できない場合は推測せず失敗させる。
- 中央検索基盤を必須とせず、各配信元を横断するfederated searchを行う。

## 対象外

- GIS I/O、ファイル解析、空間演算の再実装
- 全データのGeoDataFrame、GeoJSON、Arrow、xarray等への強制変換
- 公式データの再ホスティング
- CoreにおけるHTML scrapingやURLの推測
- 必須の中央検索インデックス
- GDAL、Rasterio、pyogrio、QGIS等のバージョン管理

## ドキュメント

- [Documentation](docs/index.md)
- [Getting started](docs/getting-started.md)
- [Configuration](docs/configuration.md)
- [API reference](docs/api.md)
- [Compatibility](docs/compatibility.md)

## 開発環境

Python 3.10以上とuvを使用します。

```console
uv sync --dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run mkdocs build --strict
uv build
```

## ライセンス

MIT Licenseです。詳細は[LICENSE](LICENSE)を参照してください。
