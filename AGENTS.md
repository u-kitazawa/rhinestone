# Rhinestone エージェントガイド

## プロジェクト構成

- `src/` レイアウトを使用する。パッケージコードは `src/rhinestone/` 配下に置き、テストを追加する場合は独立した `tests/` ディレクトリに置く。
- 設計仕様をアーキテクチャと不変条件の信頼できる唯一の情報源とする：[docs/spec_v4.md](docs/spec_v4.md)。
- Core に GDAL、Rasterio、pyogrio 等を実行時依存関係として追加しない。利用者が所有する依存は callback/factory で注入する。

## 開発コマンド

- `uv sync --dev` でプロジェクトと開発ツールをインストールする。
- `uv run pytest` でテストとカバレッジ計測を実行する。
- `uv run ruff check .` で Lint を実行する。
- `uv run ruff format --check .` でフォーマットを確認する。
- `uv run pyright` で型チェックを実行する。
- `uv build` で配布物をビルドする。
- 機能を追加するときは、対象を絞ったテストも追加する。
- プロジェクト設定を意図的に変更する場合を除き、`requires-python = ">=3.7"` 宣言との互換性を維持する。

## アーキテクチャ規則

- アクセスパイプライン `Config -> Source Adapter -> Source -> Resolver -> AccessPlan -> Resource -> Execution Adapter Selector -> Execution Adapter -> Data` を維持する。
- 責務を分離する。Source Adapter は配信元を解釈して Source を生成し、Resolver は Resource とアクセス方法を決定する。Execution Adapter は選択済み Resource を既存 OSS 向けに翻訳し、Resource の選択は行わない。
- プロバイダー固有の振る舞いを Domain 層に持ち込まない。フォーマットやプロトコル処理を再実装するのではなく、既存の標準や OSS ライブラリを優先する。
- 暗黙のフォーマット変換、URL の推測、HTML スクレイピングを避ける。検索は Search Coordinator と検索 Capability を持つ Source Adapter が公式 API を通して行う。確実に判断できない場合は、明示的に失敗させるかオプトインを要求する。
- 異なる失敗原因を `RuntimeError` にまとめず、それぞれ異なるエラー型を使用する。
- 解決処理を決定的かつ説明可能に保つ。同じ Config、メタデータ、Capability からは同じ `AccessPlan` が生成されなければならない。

## 変更時の規律

- 実例による仕様化、仕様適合テスト、垂直スライスに従う。新しい Source Adapter には、代表的な Fixture、期待される Source・Resource・AccessPlan、仕様適合テストを追加する。
- Config を不変に保ち、Source が保持する Metadata、raw metadata、Provenance を後続処理で破棄しない。
- 実装パターンが繰り返され、必要性が裏付けられるまでは外部 Adapter API を設計しない。初期段階では内部 Adapter Registry で十分である。
- 変更を最小限に抑え、振る舞いを変更した場合は仕様またはドキュメントを更新する。
