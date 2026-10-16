# 直接指定の提供元アダプター

`DirectAdapter` は利用者が明示した単一配信の `Reference` を `Resource` に変換します。

- Adapter 種別（`adapter_type`）: `direct`
- `Reference.parameters` の必須項目: `uri`, `format`
- 任意項目: `media_type`, `metadata`, `archive`, `encoding`, `layer`, `subdataset`

`direct`は`configure()`で自動登録されるため、Providerを追加する必要はありません。
`app.load(Reference("direct", parameters={...}))`でResourceを構築し、
`app.open(resource, library, runtime=...)`または`resource.open(library, runtime=...)`で開きます。

URL、形式、Runtimeは推測しません。GDAL・Rasterio・pyogrioのRuntimeはReferenceへ含めず、
`open(..., runtime=...)`へ渡します。直接loadではProviderへのHTTP通信は行いません。
使用例は[APIリファレンス](../../../../../docs/api/adapters/direct.md)を参照してください。
設定は [schema.json](schema.json) で補完・構造検証できます。
