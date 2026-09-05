# e-Stat Source Adapter

`EStatAdapter` は e-Stat API 3.0 の統計表メタデータを `Source` に変換します。

- `source_type`: `estat`
- 必須設定: `stats_data_id`
- 任意設定: `endpoint`
- 検索: `text`, `limit`
- 注入: `get_json(url, params)` と `app_id` または `api_key` のどちらか一方。

API の `getMetaInfo` と `getStatsList` を使用し、認証情報を Provenance へ保存しません。
