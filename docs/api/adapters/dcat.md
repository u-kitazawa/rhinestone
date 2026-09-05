# DcatAdapter

`DcatAdapter` は明示した DCAT RDF catalog の Dataset を解決します。

[Source Adapter 一覧](../source-adapters.md) · source type: `dcat`

## 設定

`Config.settings` は catalog の `uri` と Dataset URI の `dataset` が必須です。
`serialization` は `json-ld`、`turtle`、`xml`、`distribution` は任意です。

## Catalog と runtime

コンストラクタには document を取得する `get_document(uri)` と、RDF runtime を返す
`rdf_runtime_factory()` を渡します。`dcat:downloadURL` を持つ Distribution のみを
候補にし、`accessURL` だけの Distribution は解決しません。検索は `text` と
`limit` を使えます。

Distribution URI を指定して pyogrio で開く例は、リポジトリ checkout の
`examples/11_dcat_dataset/README.md` にあります。
