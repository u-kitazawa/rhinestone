# ODPTの提供元アダプター

`OdptAdapter` は ODPT v4 のservice queryを `Resource` と `AccessPlan` に変換します。

- Adapter 種別（`adapter_type`）: `odpt`
- `Reference.parameters`の必須項目: `dataset` (`station`, `railway`, `train`), 論理credential名の`credential`
- 任意項目: 公式フィールドだけを含む `filters`
- 実行: `app.open(reference_or_resource, "json-service")`。標準構成では組み込みHTTP Runtimeを使用します。

load時にはODPT APIを呼び出しません。consumer keyは`open()`時にcredential factoryから取得し、
Reference・Resource・AccessPlanへ保存しません。接続先とresource typeはProvider設定から渡されます。
認証付き request の構築は JSON service 実行側の `prepare_odpt_request` が担当し、
`OdptAdapter` を実行側から呼び出しません。宛先認可後に論理 credential を解決します。
設定と実行例は[APIリファレンス](../../../../../docs/api/adapters/odpt.md)を参照してください。
設定は [schema.json](schema.json) で補完・構造検証できます。
