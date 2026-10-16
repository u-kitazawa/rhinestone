# CKANの提供元アダプター

`CkanAdapter` は CKAN Action API の配信情報を `Resource` に変換します。

- Adapter 種別（`adapter_type`）: `ckan`
- Provider設定: `endpoint`。`spatial_search=True`で対応サイトのbbox検索を有効にできます。
- 直接loadの`Reference.parameters`: `resource_id`が必須。
- 検索: `text`, `format`, `limit`。`spatial_search=True`の場合のみ`bbox`にも対応。
- 注入: `get_json(url, params)`。認証は `credential` に論理名を指定し、`credentials` のRegistryから取得します。

直接loadは`resource_show`と`package_show`、検索は`package_search`を使用します。
検索は配信単位のResourceを返し、`limit`は形式照合後のResource数を数えます。
配布URLはAPIの宣言から取得し、推測しません。入出力とページングの詳細は
[APIリファレンス](../../../../../docs/api/adapters/ckan.md)を参照してください。
設定は [schema.json](schema.json) で補完・構造検証できます。
