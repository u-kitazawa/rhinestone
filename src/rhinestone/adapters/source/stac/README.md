# STACの提供元アダプター

`StacAdapter` は STAC APIと静的STACのItem assetを配信単位の `Resource` に変換します。

- Adapter 種別（`adapter_type`）: `stac`
- Provider設定: API型は `endpoint`、静的型は `catalog_uri`（排他的）。
- 直接loadのReference: `collection_id`, `item_id`, `asset_key`。静的型では `item_href` も必要。
- 検索: `bbox`, `time`, `limit`
- 注入: `get_json(url, params)`。`credential` に論理名を指定し、`credentials` のRegistryから認証情報を取得します。

API型・静的型のどちらも各data assetを独立Resourceとして返し、
複数assetのItemでも先頭assetを暗黙選択しません。
data assetがないItemや不正Itemはスキップし、diagnosticsで理由を確認できます。
静的型は公式のchild/itemリンクを有界に巡回します（`max_documents`、既定100）。
条件はItem取得後に適用し、Collection extentによる枝刈りは現在行いません。
asset URLやフォーマットは推測しません。詳細は
[APIリファレンス](../../../../../docs/api/adapters/stac.md)を参照してください。
設定は [schema.json](schema.json) で補完・構造検証できます。
