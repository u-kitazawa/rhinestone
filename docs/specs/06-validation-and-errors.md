# 信頼性とエラー

> **文書ステータス: 履歴資料。** v0.4の設計を実装境界へ整理した文書で、現行APIの契約ではありません。現在の参照先は[ドキュメントの位置付け](../documentation-status.md)を確認してください。

## 信頼性モデル

Rhinestone は provider の知名度ではなく、検証可能性、再現可能性、明示的な失敗によって信頼性を確保します。

- スキーマ検証
- 意味の検証
- Resourceの明示的な選択
- 必要な場合のチェックサム検証
- 出典情報の保持
- 暗黙のフォールバックを行わない

## 判断規則

```text
certain   -> automate
heuristic -> explicit warning or opt-in
unknown   -> fail
```

URL suffix、redirect、HTML、response body の観察から未提示の format や Resource を推測してはなりません（MUST NOT）。

## エラー分類

異なる原因を単一の `RuntimeError` にまとめません。少なくとも次の失敗を、呼び出し側が型または安定した code で区別できるようにします。

- Config の構造・値が不正
- Source type または検索条件が未対応
- provider metadata の取得失敗
- provider response の schema/semantic 不正
- Resource 候補を一意に選択できない
- 明示条件に一致する Resource 候補がない
- credential が未設定、または credential factory が失敗した
- format、protocol、access method が未対応
- Execution Adapter または runtime dependency が利用不能
- Resource へのアクセス失敗
- checksum 等の完全性検証失敗

予期される外部例外は原因を保持した境界エラーへ変換します。Programming Error や内部不変条件違反を無差別に包んではなりません（MUST NOT）。秘密情報、credential、無制限の raw payload をエラーやログへ含めません（MUST NOT）。

Adapter は `ResourceCandidate.attributes` の `matches_config`、`access_kind`、`access_options` を使って明示選択と access-plan 情報を渡せます。`matches_config` は boolean、`access_kind` は `file`、`remote-dataset`、`service-query` のいずれか、`access_options` は object でなければなりません。不一致候補は Source に保持したまま Resolver が除外します。残る候補がゼロなら `ResourceNotFoundError`、複数なら `AmbiguousResourceError` とします。
