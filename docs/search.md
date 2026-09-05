# データを検索する

`app.search()` は、登録済みで検索機能を持つ Source Adapter を横断して検索します。
戻り値は provider ごとにグループ化された `SearchResult` の辞書です。

## 検索できる Adapter を構成する

以下は CKAN と e-Stat を同時に検索する構成です。`get_json` の実装は
[アプリケーションを構成する](configuration.md)を参照してください。

```python
import os

from rhinestone import SearchQuery, configure
from rhinestone.adapters import CkanAdapter, EStatAdapter

app = configure(
    dependencies={},
    source_adapters=(
        CkanAdapter(
            get_json=get_json,
            endpoint="https://www.geospatial.jp/ckan",
        ),
        EStatAdapter(
            get_json=get_json,
            app_id=os.environ["ESTAT_APP_ID"],
        ),
    ),
    execution_adapters=(),
)
```

e-Stat は application ID が必要です。CKAN の protected API を使う場合は
`CkanAdapter(..., api_token=...)` または `api_key=...` を指定します。一方だけを指定
してください。

## 検索して結果を表示する

```python
results_by_provider = app.search(SearchQuery(text="人口", limit=10))

for provider, results in results_by_provider.items():
    print(provider)
    for index, result in enumerate(results):
        print(index, result.title)
        print(" ", result.description or "説明なし")
```

`results_by_provider["ckan"]` のように provider を選んでください。検索結果が空の
provider もあり得るため、インデックスで選ぶ前に件数を確認します。

```python
ckan_results = results_by_provider.get("ckan", ())
if not ckan_results:
    raise LookupError("CKAN で該当するデータが見つかりませんでした")

selected = ckan_results[0]
```

## 検索結果を解決する

`SearchResult` は表示専用ではありません。`to_config()` で通常の解決フローに戻します。

```python
resource = app.resolve(selected.to_config())

print(resource.uri)
print(resource.format)
print(resource.metadata.title)
print(resource.provenance.provider)
```

検索で見つけた結果も、Config validation と Resource selection を必ず通ります。provider
固有の ID を取り出して Config を作り直す必要はありません。

## 検索条件の注意点

`SearchQuery` には `text`、`bbox`、`time`、`limit` を指定できます。ただし、同時に
登録した**すべての検索 Adapter**が、指定した条件を扱える必要があります。たとえば
CKAN と e-Stat は `text` と `limit`、STAC と OGC API Features は `bbox`、`time`、
`limit` に対応します。

条件を扱えない Adapter が一つでもあると `UnsupportedSearchConditionError` になります。
空間範囲で検索したい場合は、対応する Adapter だけで別の `app` を構成してください。

```python
stac_app = configure(
    dependencies={},
    source_adapters=(stac_adapter,),
    execution_adapters=(),
)
results = stac_app.search(
    SearchQuery(bbox=(139.5, 35.5, 140.0, 36.0), limit=10)
)
```

環境変数を使う完全な実行例は、リポジトリ checkout の
`examples/07_search_and_fetch/README.md` にあります。
