# ブランチ運用方針

Rhinestoneは、開発中の変更と公開済みの状態を別ブランチで管理します。通常の変更を`main`へ直接統合せず、統合先を`develop`に統一します。

## ブランチの責務

| ブランチ | 責務 |
| --- | --- |
| `develop` | feature、fix、docsなど通常の変更を統合する。次回リリース候補を表す |
| `main` | 公開済みでリリース可能な状態を表す。GitHub Pagesとリリースの境界にする |

GitHubのdefault branch設定はこの方針に合わせて管理します。設定が切り替わるまで、コマンドやPRでは対象ブランチを明示してください。

## Pull Requestの流れ

- 通常の変更は、作業ブランチから`develop`へ送る。
- `main`へのPRは、`develop`からのrelease promotion、または`hotfix/*`からの緊急修正に限る。
- release promotionは`develop`の内容を`main`へ反映するPRとして作成する。squash mergeを許可する。
- `main`にhotfixを反映した場合は、同じ変更を`main`から`develop`へ戻すPRを必ず作成する。還流が完了するまで次のpromotionを開始しない。

docs-onlyの変更も通常は`develop`を経由します。公開済みドキュメントの緊急修正だけをhotfixとして扱います。

## 公開とリリース

- GitHub Pagesは`main`へのpushでのみデプロイする。
- developのドキュメントは本番Pagesを上書きしない。previewや別パスでの公開は別途定義する。
- PyPIリリースに使用するタグは`main`の履歴上にあるコミットへ付ける。

## 初回同期

`main`と`develop`に分岐した履歴がある場合は、最初に`main`を`develop`へnon-fast-forward mergeで取り込みます。その後、`develop`から`main`へのpromotionを行い、両ブランチの内容を同じ公開境界へ揃えます。

promotion中に`develop`へ追加変更が入った場合は、promotion PRの対象スナップショットをそのリリース範囲として扱います。
