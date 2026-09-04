# Rhinestone

Rhinestone は、配信元やファイル形式が異なる地理空間・公共データへ、統一された手順でアクセスするための Python ライブラリです。

利用するデータがすでに特定されていることを前提に、配信元のメタデータを取得・検証し、説明可能なアクセスプランを作成して、実際の読み込みを既存の OSS ライブラリへ委譲します。

> Reference in, usable data out.

## 現在の状態

このプロジェクトは設計・初期実装段階です。

- 詳細なアーキテクチャと不変条件は定義済みです。
- v0.x の実装仕様は提案段階です。
- パッケージの公開 API は、まだプレースホルダーのみです。
- 最初の垂直スライスとして、CKAN 上の GeoPackage の読み込みを予定しています。

現時点では、実用目的でインストールできる完成版ではありません。

## 目標

Rhinestone は、次の一方向パイプラインを提供します。

```text
Config
  -> DataReference
  -> SourceMetadata
  -> AccessPlan
  -> Execution
  -> Data
```

主な設計目標は次のとおりです。

- 配信元ごとの差異を吸収し、共通の読み込み体験を提供する。
- メタデータから実行方法を決定する過程を、決定的かつ説明可能にする。
- データ形式の処理を再実装せず、pyogrio などの既存 OSS に委譲する。
- 設定、参照、メタデータ、アクセスプランを明確に分離する。
- 判断できない形式やアクセス方法を暗黙に推測せず、明示的に失敗させる。

## 対象外

Rhinestone は、データを探すための検索エンジンやカタログではありません。

- 自然言語やキーワードによるデータセット検索
- カタログサイトやデータ一覧 UI
- GIS ビューアーや可視化機能
- 公式データの再ホスティング
- 大規模な結合、空間解析、形式変換などの汎用 ETL

## 予定している API

最終的には、次のような簡潔な API を提供する予定です。

```python
import rhinestone

data = rhinestone.load(
    {
        "source": {
            "type": "ckan",
            "endpoint": "https://example.jp/api/3",
            "resource_id": "abcdef",
        }
    }
)
```

読み込み前にアクセスプランを確認する経路も提供します。

```python
access_plan = rhinestone.plan(config)
data = rhinestone.execute(access_plan)
```

これらの API はまだ実装されていません。確定した振る舞いは、実装仕様を参照してください。

## ドキュメント

- [設計仕様](docs/spec_v2.md)：プロダクトの目的、スコープ、アーキテクチャ
- [実装仕様](docs/specs/README.md)：v0.x の実装可能・テスト可能な要件
- [開発エージェント向けガイド](AGENTS.md)：開発規則と検証コマンド

設計仕様と実装仕様が矛盾する場合は、実装前に文書上で解消します。

## 開発環境

### 必要なもの

- Python 3.7 以上
- [uv](https://docs.astral.sh/uv/)

### セットアップ

プロジェクトと開発ツールをインストールします。

```console
uv sync --dev
```

### 品質チェック

```console
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv build
```

テストでは Line Coverage と Branch Coverage の両方で 100% を必須とします。

## ライセンス

ライセンスはまだ定められていません。
