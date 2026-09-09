# DcatAdapter

`DcatAdapter` は明示した DCAT RDF catalog の Dataset を解決します。

[Source Adapter 一覧](../source-adapters.md) · source type: `dcat`

## 設定

`Config.settings` は catalog の `uri` と Dataset URI の `dataset` が必須です。
`serialization` は `json-ld`、`turtle`、`xml`、`distribution` は任意です。

## Catalog と runtime

標準の`configure()`経路ではDCAT文書の取得にRhinestoneの組み込みHTTP transportを使い、RDF解釈runtimeだけを`dependencies={"rdflib": ...}`として利用者が供給します。`dcat:downloadURL` を持つ Distribution のみを候補にし、`accessURL` だけの Distribution は解決しません。検索は `text` と `limit` を使えます。

Adapterを直接構築する内部テストや再利用用途では、document取得callbackとRDF runtime factoryをconstructorへ注入できます。

Distribution URI を指定して pyogrio で開く例は、リポジトリ checkout の `examples/11_dcat_dataset/README.md` にあります。
