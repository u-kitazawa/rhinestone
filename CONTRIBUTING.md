# Contributing to Rhinestone

Rhinestoneへのコントリビューションを歓迎します。バグ修正、機能追加、Source Adapterの追加、ドキュメント改善、テストの改善などを提案できます。

Rhinestoneは、日本の公的・地理空間データへアクセスするためのKnowledge / Specification Layerです。変更を始める前に、[README](README.md) と [設計仕様](docs/spec_v4.md) を確認してください。

## 基本方針

- 設計仕様と既存の不変条件を優先する。
- 変更の責務を適切な層に置く。
- CoreにGDAL、Rasterio、pyogrioなどのGIS処理系を実行時依存として追加しない。
- Source固有の知識はSource AdapterまたはCatalogに閉じ込める。
- URLの推測、暗黙のフォーマット変換、HTML scrapingを追加しない。
- 振る舞いを変更した場合は、テスト、仕様、またはドキュメントも更新する。
- 公開APIを変更する場合は、後方互換性の要否と影響をPRに明記する。

Source Adapterを追加・変更する場合は、代表的なFixture、期待されるSource・Resource・AccessPlan、仕様適合テストを一緒に追加してください。組み込みSourceの接続先や静的な仕様は、可能な限りCatalogで管理します。

## 開発環境

開発にはPython 3.10以上と[uv](https://docs.astral.sh/uv/)を使用します。

リポジトリを取得したあと、次のコマンドで開発環境を準備します。

```console
uv sync --dev --locked
```

ロックファイルを更新する必要がある場合は、変更理由をPRに記載してください。

## リポジトリ構成

主なディレクトリとファイルは次のとおりです。

- `src/rhinestone/`: パッケージ本体
- `tests/`: テスト
- `docs/`: 利用者向けドキュメントと設計仕様
- `src/rhinestone/catalogs/`: 組み込みSourceのCatalog
- `pyproject.toml`: パッケージ、開発ツール、型チェックの設定
- `.github/workflows/`: CIとドキュメント公開の設定

## ローカル検証

PRを作成する前に、CIと同じ主要チェックを実行してください。

```console
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
NO_MKDOCS_2_WARNING=1 uv run mkdocs build --strict
uv build
```

`pytest` はカバレッジも計測し、プロジェクト設定で定めた基準を満たさない場合に失敗します。

CIでは、これらに加えてPython 3.10〜3.13での実行と、ビルドしたwheelをクリーンな仮想環境へインストールして読み込む検証を行います。

## Issueから作業を始める

機能追加や設計変更を行う場合は、まず既存のIssueを確認してください。

1. 既存Issueに同じ目的の議論がないか確認する。
2. 新しい変更の場合はIssueを作成し、目的、背景、対象範囲、想定するAPIや挙動を記載する。
3. 小さな修正でIssueが不要な場合でも、変更理由がPR本文から分かるようにする。
4. 仕様変更を伴う場合は、実装前に `docs/spec_v4.md` との整合性を確認する。

大きな設計変更や公開APIの変更は、実装を始める前にIssueで方向性を確認してください。

## ブランチを作成する

`main` を最新状態にしてから、目的が分かるブランチを作成します。

```console
git switch main
git pull origin main
git switch -c <type>/<short-description>
```

既存の履歴では、次のような接頭辞を使用しています。

- `feat/`: 機能追加
- `fix/`: バグ修正
- `docs/`: ドキュメント変更
- `refactor/`: 動作を維持した構造変更
- `test/`: テスト変更
- `build/`: パッケージングやビルド設定の変更
- `style/`: 動作を変えない整形・スタイル変更

ブランチ名は短く具体的にしてください。例：

```text
feat/add-new-source
fix/resolve-invalid-config
docs/update-contributing-guide
```

## 実装とコミット

変更はレビューしやすい単位に分けてください。

- 実装、テスト、ドキュメントを変更内容に合わせて更新する。
- 無関係なリファクタリングや大規模な整形を同じPRに混在させない。
- 新しい外部依存を追加する場合は、必要性、実行時依存か開発時依存か、代替案をPRに記載する。
- 秘密情報、APIキー、個人情報をコミットしない。
- コミットメッセージは、既存の履歴に合わせて `type: summary` 形式を推奨する。

例：

```text
feat: add source catalog loader test
fix: reject incomplete access plan
docs: explain static source configuration
refactor: simplify source composition
```

## Pull Requestを作成する

実装とローカル検証が完了したら、ブランチをpushします。

```console
git push -u origin <type>/<short-description>
```

GitHubで、作業ブランチから `main` へのPull Requestを作成してください。

PR本文には、少なくとも次の内容を含めます。

```markdown
## 概要

何を変更したか、なぜ変更したかを簡潔に説明します。

## 変更内容

- 変更点1
- 変更点2

## 検証

- [ ] `uv run pytest`
- [ ] `uv run ruff check .`
- [ ] `uv run ruff format --check .`
- [ ] `uv run pyright`
- [ ] `NO_MKDOCS_2_WARNING=1 uv run mkdocs build --strict`
- [ ] `uv build`

## 影響・注意点

公開APIの変更、互換性への影響、未対応の事項があれば記載します。

Fixes #<issue-number>
```

Issueを自動的にクローズしない場合は、`Fixes #<issue-number>` ではなく、関連Issueへのリンクや `Refs #<issue-number>` などを使用してください。

PRのタイトルも、コミットと同様に変更の種類が分かる形式にします。

```text
feat: add ...
fix: correct ...
docs: update ...
refactor: move ...
```

## レビューと修正

PRを作成すると、GitHub Actionsがテスト、Lint、型チェック、ドキュメントのビルド、パッケージのビルドを実行します。

レビューで修正を求められた場合は、同じブランチに追加コミットをpushしてください。

```console
git add <changed-files>
git commit -m "fix: address review comments"
git push
```

新しいPRを作り直すのではなく、既存のPRを更新します。PR本文の検証結果と変更概要も、必要に応じて更新してください。

## マージまでの流れ

1. IssueまたはPR本文で変更の目的と範囲を確認する。
2. CIがすべて成功していることを確認する。
3. レビューコメントへ対応し、必要な追加テストを行う。
4. 承認後、メンテナーが`main`へマージする。
5. `main`へのマージ後、ドキュメント公開workflowがMkDocsを実行してGitHub Pagesへ反映する。

このリポジトリでは、PRのマージ方法や権限設定はGitHubリポジトリの設定に従います。マージ前に、CIの失敗を無視したり、未確認の変更を残したりしないでください。

## ドキュメントの変更

利用者向けドキュメントは`docs/`に置きます。ナビゲーションを変更する場合は、MkDocsの設定とリンク切れも確認してください。

ドキュメントだけの変更でも、次のコマンドを実行します。

```console
NO_MKDOCS_2_WARNING=1 uv run mkdocs build --strict
```

不明点や設計上の相談は、実装を大きく始める前にIssueまたはDraft PRで共有してください。
