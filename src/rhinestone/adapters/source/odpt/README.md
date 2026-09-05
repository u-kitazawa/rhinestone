# ODPT Source Adapter

`OdptAdapter` は ODPT v4 の service query を `Source` に変換します。

- `source_type`: `odpt`
- 必須設定: `dataset` (`station`, `railway`, `train`), `credential`
- 任意設定: 公式フィールドだけを含む `filters`
- 実行: `JsonServiceAdapter` に `OdptAdapter.prepare_request` を渡します。

この Adapter は API を呼び出しません。consumer key は `CredentialRegistry` から実行時に取得し、Source へ保存しません。
設定は [schema.json](schema.json) で補完・構造検証できます。
