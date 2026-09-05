# CKAN Source Adapter

`CkanAdapter` は CKAN Action API の resource を `Source` に変換します。

- `source_type`: `ckan`
- 必須設定: `resource_id`
- 任意設定: `endpoint`
- 検索: `text`, `limit`
- 注入: `get_json(url, params)`。認証は `api_token` または `api_key` のどちらか一方です。

`resource_show` と `package_show` の公式 API だけを使用し、配布 URL は推測しません。
設定は [schema.json](schema.json) で補完・構造検証できます。
