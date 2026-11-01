# DCATの提供元アダプター

`DcatAdapter` は明示された DCAT RDF catalog の配信を `Resource` に変換します。

- Adapter 種別（`adapter_type`）: `dcat`
- 直接loadの`Reference.parameters`: `uri`, `dataset`が必須。
- 任意項目: `serialization` (`json-ld`, `turtle`, `xml`), `distribution`
- 検索: `text`, `limit`
- 標準構成: 文書取得は組み込みHTTP transport、RDF解釈用Runtimeは`configure(dependencies={"rdflib": ...})`で供給します。

検索は`dcat:downloadURL`を持つDistributionから配信単位のResourceを返します。
`accessURL`だけのDistributionは対象外です。直接loadで配信を一意に選べなければ
暗黙に先頭を選ばず失敗します。Dataset URIとdistributionを明示的に検証し、
RDFの取得・解析失敗をProvider境界エラーとして返します。
Providerの`catalog_uri`による取得先検証、Runtimeの遅延供給、エラー区分は
[APIリファレンス](../../../../../docs/api/adapters/dcat.md)を参照してください。
設定は [schema.json](schema.json) で補完・構造検証できます。
