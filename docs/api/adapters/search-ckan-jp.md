# SearchCkanJpAdapter（横断CKAN検索アダプター）

`SearchCkanJpAdapter` は search.ckan.jp Backend API を使って複数のCKANカタログを検索し、
元の配布物を解決する `Result` を返します。

[Source Adapter 一覧](../source-adapters.md) · source type: `search-ckan-jp`

## 設定と検索

組み込みCatalogの `sources.SEARCH_CKAN_JP` に検索先が定義されています。検索には `text`
が必須で、`limit` を指定できます。`limit` はBackend APIへの package 件数だけでなく、
package内の対応するresourceへ展開した最終結果にも適用されます。

```python
from rhinestone import configure, sources

app = configure(sources=(sources.SEARCH_CKAN_JP,))
results = app.search(text="河川", limit=10)
```

このSourceはDiscovery専用です。検索結果の `target` は元の配布URL、形式、metadataを持つ
`direct` Configに設定されるため、通常どおり `app.resolve(result)` または `result.resolve()`
でResourceへ解決できます。`Config("search-ckan-jp", ...)` を直接解決することはできません。

検索結果には検索元の `metadata`、`raw_metadata`、`provenance` が保持されます。解決先が
`direct` の場合、これらは `Resource.discovery` に保存され、配布物側のmetadataやprovenance
とは分離されます。

## 対応範囲

- search.ckan.jpが返すpackage/resourceの識別情報と公式配布URLを利用します。
- resourceの形式またはMIME typeが明示されている結果だけを返します。
- HTMLの解析、配布URLの推測、検索結果からのprovider secretの取得は行いません。
- 検索結果に含まれる元カタログURLは出典として保持しますが、検索専用Sourceから直接取得は行いません。
