# Rhinestone

Rhinestone は、日本の公的・地理空間データを既存 OSS から利用するための Knowledge / Specification Layer です。配信元、API、フォーマット、配信方式に関する知識を蓄積し、対象データを解釈して、利用可能な Resource と AccessPlan を生成します。

Rhinestone 自身は GIS データ処理エンジンを実装しません。GDAL、Rasterio、pyogrio、PyArrow などがデータの読み込み・変換・解析を担い、Rhinestone はそれらへ渡す URI、オプション、レイヤーやサブデータセットの指定を組み立てます。

## 現在の状態

このプロジェクトは設計・初期実装段階です。公開 API と対応 Adapter は、仕様に基づいて段階的に実装します。

## アーキテクチャ

通常のアクセスフローは次のとおりです。

```text
Config
  -> [Source Adapter]
  -> Source
  -> [Resolver]
  -> AccessPlan
  -> Resource
  -> [Execution Adapter Selector]
  -> [Execution Adapter]
  -> user-provided dependency
  -> Data
```

検索は各配信元の公式 API へ横断的に問い合わせます。

```text
SearchQuery
  -> [Search Coordinator]
  -> [Source Adapter]...
  -> SearchResult[]
  -> Config
```

SearchResult は Config へ変換した後、通常の検証・解決フローに入ります。

## 設計原則

- データそのものではなく、データへのアクセス方法を統一する。
- 配信元固有の知識は Source Adapter に閉じ込める。
- 解決済みの Metadata と Provenance を Resource まで保持する。
- 実行方法の選択を決定的かつ説明可能にする。
- 実行時依存は利用者が所有し、callback/factory として供給する。
- 公式の機械可読インターフェースを使い、Core では HTML scraping を行わない。
- 確実に判断できない場合は、推測せず失敗させるか明示的な opt-in を求める。
- 中央検索基盤を必須とせず、各配信元を横断する federated search を行う。

## 概念的な利用例

Config は利用したいデータを宣言し、HTTP や GDAL の実装詳細を含めません。

```yaml
providers:
  gspace:
    adapter_type: ckan
    settings:
      endpoint: https://example.jp
config:
  source_id: gspace
  settings:
    resource_id: abcdef
```

実行時のライブラリは利用者が供給します。

```python
rhinestone.configure(
    providers={
        "gspace": ProviderConfig(
            "ckan", {"endpoint": "https://example.jp"}
        )
    },
    dependencies={
        "http-json": lambda: get_json,
        "gdal": lambda: osgeo.gdal,
        "rasterio": lambda: rasterio,
    }
)
```

利用者はprovider設定とdependencyを渡します。Source AdapterとExecution Adapterは
Rhinestoneが組み立てます。同じAdapter種別を利用する複数providerも、異なるsource idで
同時に構成できます。

Resource は URI だけでなく、format、media type、Metadata、Provenance、AccessPlan、Source を保持します。必要に応じて実行 Adapter を明示できます。

```python
resource.open(adapter="gdal")
```

コード例は設計上の概念を示すものであり、未実装の公開 API を保証するものではありません。

## 対象外

- GIS I/O、ファイル解析、空間演算の再実装
- 全データの GeoDataFrame、GeoJSON、Arrow、xarray などへの強制変換
- 公式データの再ホスティング
- Core における HTML scraping や URL の推測
- 必須の中央検索インデックス
- GDAL、Rasterio、pyogrio、QGIS などのバージョン管理

## ドキュメント

- [ドキュメント](docs/index.md)：利用者向けの入口
- [Getting started](docs/getting-started.md)：インストールと最短の利用例
- [API リファレンス](docs/api.md)：公開 API、モデル、Adapter、エラー
- [対応状況と既知の非対応](docs/compatibility.md)：provider、format、runtime の互換性
- [開発エージェント向けガイド](AGENTS.md)：開発規則と検証コマンド

## 開発環境

Python 3.10 以上と [uv](https://docs.astral.sh/uv/) を使用します。

```console
uv sync --dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv build
```

## ライセンス

MIT License です。詳細は [LICENSE](LICENSE) を参照してください。
