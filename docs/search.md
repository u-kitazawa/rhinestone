# データを検索する

`app.search()`は、構成済みで検索Capabilityを持つSourceを横断して検索します。戻り値は`source_id`ごとにグループ化された`SearchResult`の辞書です。

## 組み込みSourceを検索する

```python
import os

from rhinestone import SearchQuery, configure, sources

app = configure(
    sources=(sources.GEOSPATIAL_JP, sources.ESTAT),
    dependencies={"http-json": lambda: get_json},
    credentials={"estat": lambda: os.environ["ESTAT_APP_ID"]},
)

results_by_source = app.search(SearchQuery(text="人口", limit=10))
```

e-Statのapplication IDはcredentialとして渡します。SourceDefinitionや検索結果へsecretを保存しません。

## 結果を選ぶ

```python
for source_id, results in results_by_source.items():
    print(source_id)
    for index, result in enumerate(results):
        print(index, result.title)

ckan_results = results_by_source.get("geospatial-jp", ())
if not ckan_results:
    raise LookupError("該当するデータが見つかりませんでした")

selected = ckan_results[0]
```

`SearchResult`は`source_id`と、そのSource内の対象を表す`settings`を保持します。endpointなどSourceDefinition側の値は検索結果へ複製しません。

## Configへ戻して解決する

```python
config = selected.to_config()
resource = app.resolve(config)

print(config.source_id)
print(config.settings)
print(resource.uri)
print(resource.provenance.provider)
```

検索結果も必ず通常の`Config -> resolve -> Resource`フローへ戻します。

## 検索条件

`SearchQuery`には`text`、`bbox`、`time`、`limit`を指定できます。ただし、同じappに構成した検索可能Sourceが指定条件を扱える必要があります。扱えないSourceがある場合は`UnsupportedSearchConditionError`になります。

例えばSTACだけを空間範囲検索する場合は、組み込み定義がまだないためcustom Sourceを明示します。

```python
from rhinestone import SourceDefinition

stac_app = configure(
    sources=(
        SourceDefinition(
            "imagery",
            "stac",
            {"endpoint": "https://stac.example/api"},
        ),
    ),
    dependencies={"http-json": lambda: get_json},
)
results = stac_app.search(
    SearchQuery(bbox=(139.5, 35.5, 140.0, 36.0), limit=10)
)
```

完全な実行例は`examples/07_search_and_fetch/`を参照してください。
