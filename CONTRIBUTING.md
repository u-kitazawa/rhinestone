# Rhinestoneへの貢献

Rhinestoneへのコントリビューションを歓迎します。バグ修正、機能追加、Source Adapterの追加、ドキュメント改善、テストの改善などを提案できます。

Rhinestoneは、日本の公的・地理空間データを使える形へ解決するPythonライブラリです。変更を始める前に、[README](README.md)と本ガイドを確認してください。

## 基本方針

- 設計仕様と既存の不変条件を優先する。
- 変更の責務を適切な層に置く。
- CoreにGDAL、Rasterio、pyogrioなどのGIS処理系を実行時依存として追加しない。
- Provider固有の知識はSource AdapterまたはCatalogに閉じ込める。
- URLの推測、暗黙のフォーマット変換、HTML scrapingを追加しない。
- 振る舞いを変更した場合は、テスト、仕様、またはドキュメントも更新する。
- 公開APIを変更する場合は旧APIを削除し、影響と移行先をPRに明記する。後方互換のための別名、wrapper、旧引数は追加しない。

Source Adapterを追加・変更する場合は、代表的なFixture、期待されるReference・Resource・AccessPlan、仕様適合テストを一緒に追加してください。
`load(reference)`は配信単位のResourceを返し、検索能力を持つAdapterの`search(query)`も
配信単位のResourceを返します。Providerは接続先・サービス設定、Catalogは構成するProviderの一覧です。
組み込みProviderの接続先や静的な仕様は、可能な限りCatalogで管理します。
拡張時の契約は[Custom Adapterを作る](docs/custom-adapters.md)を参照してください。

## 開発環境

開発にはPython 3.10以上と[uv](https://docs.astral.sh/uv/)を使用します。

リポジトリを取得したあと、次のコマンドで開発環境を準備します。

```console
uv sync --dev --locked
```

ロックファイルを更新する必要がある場合は、変更理由をPRに記載してください。

### 依存関係の脆弱性監査

Python 3.12とuvがある環境で `python scripts/audit_dependencies.py` を実行します。
`uv.lock` の直接・間接・dev依存と、Python/OS別の全解決バージョンを
PyPIの既知脆弱性情報と照合します。未公開のローカルプロジェクト自身は対象外です。
監査ツールは固定版pip-auditを隔離環境で実行し、Core依存には追加しません。
終了コード0は完全な監査の成功、1は既知脆弱性の検出、2は通信・ツール・lock不整合などによる
監査未完了です。未完了を「脆弱性なし」として扱わず、診断を確認して再実行してください。
通常の `scripts/check.sh` とは分け、Dependency audit CIでPR・pushと毎日実行します。
定期workflowはGitHubの既定ブランチ上で動くため、既定ブランチへの反映後に有効になります。

Dependabot version updatesはuvの更新PRをdevelop向けに週次作成する設定です。
設定ファイルを既定ブランチにも反映する必要があります。Dependabot alerts/security updatesの
有効化はリポジトリ設定・権限に依存し、この設定だけで有効化したとはみなしません。
alertsは既定ブランチの依存グラフを対象とし、developの監査CIを代替しません。
urllib3のセキュリティ下限値はuvのconstraintに置き、Coreの直接依存を増やさず維持します。

## リポジトリ構成

主なディレクトリとファイルは次のとおりです。

- `src/rhinestone/`: パッケージ本体
- `tests/`: テスト
- `docs/`: 現行の利用者向けガイド、APIリファレンス、開発・リリース運用
- `src/rhinestone/catalogs/`: 組み込みProviderのCatalog
- `pyproject.toml`: パッケージ、開発ツール、型チェックの設定
- `.github/workflows/`: CIとドキュメント公開の設定

## ドキュメントの更新

ナビゲーションに掲載されたガイドとAPIリファレンスは、同じブランチの実装とテストに
一致する公開契約を説明します。文書と実装が矛盾する場合は実装・テストを確認し、
公開APIや振る舞いの変更と同時に該当するガイド・APIリファレンスを更新してください。
文書のブランチと公開版の関係は[API安定性とリリース運用](docs/release-policy.md)の「文書の対象バージョン」を参照します。

設計課題・未完了事項・調査結果はGitHub Issuesで追跡します。調査には対象Issue、調査日、
確認済み事項、残る検証を記録し、未確認の提案を現行の公開契約として扱いません。
新しい設計判断を実装した場合はIssueの記録だけで完了とせず、現行文書にも反映します。
過去の仕様本文はGit履歴、versionごとの変更履歴はGitHub Releasesを参照し、
旧API例・移行マトリクス・履歴分類ページを現行文書ツリーに保持しません。

Pythonサポート範囲は`pyproject.toml`を正本とし、CIの検証範囲は[対応状況](docs/compatibility.md)に記載します。

## ローカル検証

PRを作成する前に、CIと同じ主要チェックを実行してください。コマンドはCIと共有しているため、個別に実行せず次の入口を使用します。

```console
bash scripts/check.sh
```

`pytest` はカバレッジも計測し、プロジェクト設定で定めた100%基準を満たさない場合に失敗します。テスト件数だけで成功と判断せず、コマンドの終了コードが0であることと、カバレッジ出力の`Missing`が空であることを確認してください。

CIでは、これらに加えてPython 3.10〜3.13での実行と、ビルドしたwheelをクリーンな仮想環境へインストールして読み込む検証を行います。
CIはContributorのブランチを自動修正・commit・pushしません。Ruffで失敗した場合は、
`uv run ruff check --fix .`と`uv run ruff format .`をローカルで実行して変更を確認・commitし、
`bash scripts/check.sh`を再実行してください。これにより、PRの最終commitとCIの検証対象を一致させます。

## Issueから作業を始める

機能追加や設計変更を行う場合は、まず既存のIssueを確認してください。

1. 既存Issueに同じ目的の議論がないか確認する。
2. 新しい変更の場合はIssueを作成し、目的、背景、対象範囲、想定するAPIや挙動を記載する。
3. 小さな修正でIssueが不要な場合でも、変更理由がPR本文から分かるようにする。
4. 仕様変更を伴う場合は、実装、テスト、公開ガイド、APIリファレンスを同じ変更で更新する。

大きな設計変更や公開APIの変更は、実装を始める前にIssueで方向性を確認してください。

## ブランチを作成する

通常の変更は `develop` を最新状態にしてから、目的が分かるブランチを作成します。`main` は公開済み・リリース可能な状態を表し、通常の作業ブランチの起点にはしません。

```console
git switch develop
git pull origin develop
git switch -c <type>/<short-description>
```

通常の変更を `develop` や `main` へ直接pushしてはいけません。必ず作業ブランチへcommitしてpushし、Pull Requestを経由して統合してください。`main`へのrelease promotionやhotfixも、[ブランチ運用方針](docs/branch-policy.md)に定めたPull Requestの手順に従います。

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
fix/reject-invalid-reference
docs/update-contributing-guide
```

## 実装とコミット

コミットは変更の意図を追える単位に分け、PRは次の基準でまとめてください。

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

## PRの粒度と継続作業

PRは、利用者にとって一つの目的が完了し、レビューと取り込みを一度に判断できる単位にまとめます。
ファイル数、個々の検証項目、作業時間の区切りをPRの分割基準にはしません。

- 着手前に関連Issueと未マージPRを確認する。同じ目的・原因・公開契約に属する修正、回帰テスト、文書更新は、既存PRの範囲に収まる限り同じブランチへ集約する。
- 文書監査は対象範囲を先に定め、関連ページを横断して確認し、見つかった修正をまとめる。同じ入力・例外契約に関する複数Adapterの修正も、責務と検証を整理して一つのPRにできるか検討する。
- 同じIssueでも独立した目的の変更は無理にまとめず、異なるIssueでも同じ目的の変更なら関連IssueをPR本文に列挙する。Issue番号だけで分割・集約を決めない。
- 新しいPRは、独立して取り込む必要がある変更、先行して提供する必要がある修正、依存関係やリスクが異なる変更、または一度にレビューするには大きすぎる変更に分ける。分割した場合は、各PRの完了条件・依存順序・分割理由を説明する。

一つの目的の中でも、無関係な整理を追加して範囲を広げないでください。
修正に必要な実装・テスト・文書を揃え、合意した範囲の完了を目指します。

エージェントや定期実行でも、実行回数やセッション終了を理由にPRを分割しません。
一度の実行で完了できない場合は、同じ作業ブランチを継続し、必要ならDraft PRを使います。
IssueまたはPRへ、確認済み範囲、検証結果、残件、次のアクションを記録して引き継ぎます。
「原則1件対応」は取り組むIssue・目的の選択であり、毎回新しいPRを作る意味ではありません。

進捗報告は、実装の進展、阻害要因、ユーザー判断が必要な点、取り込み準備完了などを中心にまとめます。
同じ結果の反復や、CI確認だけの細切れの通知は避け、報告頻度の明示指示がある場合はその指示に従います。

## Pull Requestを作成する

実装とローカル検証が完了したら、ブランチをpushします。

```console
git push -u origin <type>/<short-description>
```

GitHubで、通常の作業ブランチから `develop` へのPull Requestを作成してください。`main` へのPull Requestは、`develop`からのrelease promotionまたは `hotfix/*` からの緊急修正に限ります。詳細は[ブランチ運用方針](docs/branch-policy.md)を参照してください。

`develop` や `main` に直接pushして変更を統合してはいけません。Pull Requestの作成後は、CIとレビューが完了してからマージします。

PR本文には、少なくとも次の内容を含めます。

```markdown
## 概要

何を変更したか、なぜ変更したかを簡潔に説明します。

## 変更内容

- 変更点1
- 変更点2

## 検証

- [ ] `bash scripts/check.sh` が終了コード0で完了し、カバレッジ出力に未実行行がない

## 影響・注意点

公開APIの変更、互換性への影響、未対応の事項があれば記載します。

Refs #<issue-number>
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
4. 承認後、メンテナーが通常のPRを`develop`へマージする。
5. リリース時に、メンテナーが`develop`から`main`へのpromotion PRを作成してマージする。squash mergeを許可する。
6. `main`へhotfixをマージした場合は、同じ変更を`main`から`develop`へ必ず還流させる。
7. `main`へのマージ後、ドキュメント公開workflowがMkDocsを実行してGitHub Pagesへ反映する。

このリポジトリでは、PRのマージ方法や権限設定はGitHubリポジトリの設定に従います。マージ前に、CIの失敗を無視したり、未確認の変更を残したりしないでください。

## ドキュメントの変更

利用者向けドキュメントは`docs/`に置きます。ナビゲーションを変更する場合は、MkDocsの設定とリンク切れも確認してください。

ドキュメントだけの変更でも、次のコマンドを実行します。

```console
NO_MKDOCS_2_WARNING=1 uv run mkdocs build --strict
```

不明点や設計上の相談は、実装を大きく始める前にIssueまたはDraft PRで共有してください。
