# データを検索する

`app.search()`は、構成済みで検索Capabilityを持つSourceを横断して検索します。文字列を渡す通常経路では`SearchResult`のsequenceを返し、`results[0]`で最初の結果を取得できます。HTTP通信はRhinestoneの組み込みtransportを使います。Sourceごとの高度な参照では`results["source-id"]`、`items()`、`keys()`を利用できます。

## 組み込みSourceを検索する

```python
import os

from rhinestone import configure, sources

app = configure(
    sources=(sources.GEOSPATIAL_JP, sources.ESTAT),
    credentials={"estat": lambda: os.environ["ESTAT_APP_ID"]},
)

results = app.search("人口")
selected = results[0]
```

e-Statのapplication IDはcredentialとして渡します。SourceDefinitionや検索結果へsecretを保存しません。

## 結果を選ぶ

```python
for source_id, source_results in results.items():
    print(source_id)
    for index, result in enumerate(source_results):
        print(index, result.title)

ckan_results = results.get("geospatial-jp", ())
if not ckan_results:
    raise LookupError("該当するデータが見つかりませんでした")

selected = results[0]
```

`SearchResult`は`source_id`と、そのSource内の対象を表す`settings`を保持します。endpointなどSourceDefinition側の値は検索結果へ複製しません。

## Configへ戻して解決する

```python
config = selected.to_config()
resource = selected.resolve()

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
)
results = stac_app.search(
    SearchQuery(bbox=(139.5, 35.5, 140.0, 36.0), limit=10)
)
```

完全な実行例は`examples/07_search_and_fetch/`を参照してください。
