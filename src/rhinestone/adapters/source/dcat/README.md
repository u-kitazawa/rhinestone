# DCAT Source Adapter

`DcatAdapter` は明示された DCAT RDF catalog の Dataset を `Source` に変換します。

- `source_type`: `dcat`
- 必須設定: `uri`, `dataset`
- 任意設定: `serialization` (`json-ld`, `turtle`, `xml`), `distribution`
- 検索: `text`, `limit`
- 注入: catalog を読む `get_document(uri)` と利用者所有の `rdf_runtime_factory()`。

Dataset URI と distribution は明示的に検証し、RDF の取得・解析失敗を provider 境界エラーとして返します。
