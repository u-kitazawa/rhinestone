# DcatAdapter

`DcatAdapter` は明示した DCAT RDF catalog の Dataset を解決します。

[Source Adapter 一覧](../source-adapters.md) · source type: `dcat`

## 設定

`Config.settings` は catalog の `uri` と Dataset URI の `dataset` が必須です。
`serialization` は `json-ld`、`turtle`、`xml`、`distribution` は任意です。

`configure(sources=...)` で利用する場合は、Provider設定の `catalog_uri` が信頼できる取得先です。
解決時の `Config.settings["uri"]` がこの値と一致しない場合は、取得前に拒否されます。
`catalog_uri` を設定しない構成では取得先を信頼済みProvider値で検証できないため、
外部入力をそのまま `Config` に渡さないでください。

## Catalog と runtime

標準の`configure()`経路ではDCAT文書の取得にRhinestoneの組み込みHTTP transportを使い、RDF解釈runtimeだけを`dependencies={"rdflib": ...}`として利用者が供給します。遅延評価する場合は `RuntimeFactory(factory)` を指定し、DCATの`search()`または`resolve()`で初めて評価されます。未設定またはfactoryの失敗は`DependencyUnavailableError`、文書取得の失敗は`ProviderMetadataError`として区別されます。解決済みResourceやAccessPlanは`rdflib`の実体・factoryを保持しません。

`dcat:downloadURL` を持つ Distribution のみを候補にし、`accessURL` だけの Distribution は解決しません。検索は `text` と `limit` を使えます。

Adapterを直接構築する内部テストや再利用用途では、document取得callbackとRDF runtime factoryをconstructorへ注入できます。このfactoryの任意例外も`DependencyUnavailableError`へ変換され、既存の`DependencyUnavailableError`はそのまま伝播します。

Distribution URI を指定して pyogrio で開く例は、リポジトリ checkout の `examples/11_dcat_dataset/README.md` にあります。
