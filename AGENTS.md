# Rhinestone エージェントガイド

## プロジェクト構成

- `src/` レイアウトを使用する。パッケージコードは `src/rhinestone/` 配下に置き、テストを追加する場合は独立した `tests/` ディレクトリに置く。
- 現行の公開契約、移行先の設計草案、履歴資料は[ドキュメントの位置付け](docs/documentation-status.md)に従って区別する。公開APIは実装、テスト、利用者向けガイド、APIリファレンスを一致させる。
- Core に GDAL、Rasterio、pyogrio 等を実行時依存関係として追加しない。利用者が所有する依存は callback/factory で注入する。

## 開発コマンド

- `uv sync --dev` でプロジェクトと開発ツールをインストールする。
- `bash scripts/check.sh` でPR CIと同じ主要チェックを一括実行する。
- `uv run pytest` でテストとカバレッジ計測を実行する。
- `uv run ruff check .` で Lint を実行する。
- `uv run ruff format --check .` でフォーマットを確認する。
- `uv run pyright` で型チェックを実行する。
- `uv build` で配布物をビルドする。
- 機能を追加するときは、対象を絞ったテストも追加する。
- プロジェクト設定を意図的に変更する場合を除き、`requires-python = ">=3.10"` 宣言との互換性を維持する。

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

### レビュー規律

- レビューでは、PRで追加・変更された契約と、既存の明文化された不変条件に対する回帰を優先する。変更を契機としてリポジトリ全体の潜在的不備を網羅的に探索しない。
- finding は、具体的な入力と観測可能な失敗（公開契約違反、誤った解決結果、secret漏えい、非決定性、実行不能な`AccessPlan`など）で説明できるものを優先する。単なる防御的強化や一般論は blocker とせず follow-up 候補とする。
- 既存 invariant の違反と、新しい invariant や設計要求の提案を区別する。後者は当該PRで合意された scope に含まれない限り、修正必須にしない。
- 同じ invariant の境界条件は確認してよいが、その修正から別の問題領域へ scope を拡張しない。標準ライブラリや downstream runtime が責任を持つ完全な仕様準拠を重複実装するよう要求しない。
- review severity は参考情報として扱い、merge blocker かどうかは scope、contract、利用者への影響、安全性、data corruption、determinism への影響で判断する。
- 既存コードに見つかった out-of-scope finding は、必要なら Issue や follow-up PR として分離し、当該PRの完了条件に含めない。
- PR の完了条件はレビューコメントがゼロになることではなく、合意した scope と contract / invariant を満たし、CI と必要な回帰テストが通ることとする。

### 境界と不変条件

- 外部入力や Value Object は、暗黙の型変換や未知値を許容せず、ドメイン上の不変条件を満たす場合だけ受け入れる。
- domain identity、provider 固有 metadata、raw data、正規化済みデータ、内部制御情報を区別し、それぞれの責務を混在させない。
- 公開インターフェースを利用するコードは、その契約に含まれない内部実装へ依存しない。
- 変更時は局所的な修正だけでなく、値が生成されてから消費されるまでの経路を確認し、エラー分類・データ保持・性能を含めて一貫した振る舞いを保証する。
