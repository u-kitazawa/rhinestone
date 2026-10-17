# ドキュメントの位置付け

Rhinestoneの利用者向けドキュメントは、同じブランチの実装とテストに一致する
「現行の公開契約」を説明します。過去の仕様はGit履歴、設計課題はGitHub Issuesで追跡します。

「現行」は文書と同じブランチの実装を指します。`develop`は次回リリース候補、`main`と
GitHub Pagesは公開済みの境界です。`pip install rhinestone`で入るPyPI版の契約は、
対応するリリースタグの文書で確認してください。developの利用方法は
[はじめに](getting-started.md)に記載しています。

## 現行の公開契約

利用者向けの現行契約は、ナビゲーションに掲載されたガイドとAPIリファレンスです。公開APIの正確なシグネチャと振る舞いは、`src/rhinestone/`の実装および`tests/`のテストと一致しなければなりません。

- [はじめに](getting-started.md)
- [ガイド](search.md)
- [目的別チュートリアル](tutorials/index.md)
- [APIリファレンス](api.md)
- [対応状況](compatibility.md)
- [Runtimeの導入ガイド](runtimes.md)
- [API安定性とリリース運用](release-policy.md)

文書と実装が矛盾する場合は、実装とテストを確認し、同じ変更で公開ドキュメントを更新します。

## 設計課題と保留案

設計課題と未完了事項はGitHub Issuesで追跡します。旧v0.5設計草案の現行契約との照合と
未採用構想の引継ぎは[文書整理Issue](https://github.com/u-kitazawa/rhinestone/issues/213#issuecomment-6197006931)に残しています。
旧API例や過去の採用候補を、現在の公開契約や暗黙の実装要件として扱いません。

旧移行マトリクスの保留事項と
撤去の引継ぎ記録は[文書整理Issue](https://github.com/u-kitazawa/rhinestone/issues/213#issuecomment-6166381400)に残しています。
過去の実装状態はGit履歴を参照し、現行APIの契約には上記の公開ガイド・実装・テストを使います。

## 調査記録

`research/` は、実装前の調査結果と未確認事項を保存する開発用資料です。
現行の公開契約や承認済みの仕様ではなく、MkDocsの公開ビルド対象から除外します。
各記録には対象Issue、調査日、確認済み事項、残る検証を明記します。

## 履歴資料

旧v0.4仕様の全文監査と未採用構想の引継ぎは
[文書整理Issue](https://github.com/u-kitazawa/rhinestone/issues/213#issuecomment-6199477176)に記録しています。
旧仕様本文はGit履歴で参照できます。旧API例や未採用構想を現行の公開契約へ戻さず、
現在の挙動は上記のガイド、APIリファレンス、実装、テストで確認してください。

## 開発時の更新規則

- 公開APIや振る舞いを変更する場合は、実装、テスト、該当する公開ガイド/APIリファレンスを同じ変更で更新します。
- 新たな設計判断を実装する場合は、Issue上の記録だけで完了とせず、現行の公開契約へ反映します。
- 過去の判断を保存する目的以外で履歴資料へ新しい契約を追加しません。
- Pythonサポート範囲は`pyproject.toml`を正本とし、現在はPython 3.10以上です。CIで検証するバージョンは[対応状況](compatibility.md)に記載します。
