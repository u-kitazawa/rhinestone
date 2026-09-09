# データを検索する

`app.search()`は構成済みProviderを横断してResultを返します。

## 文字列と検索パラメータ

```python
results = app.search(text="人口", limit=10)
```

`text`、`bbox`、`time`、`limit`をキーワードで指定できます。高度な用途では`SearchQuery`を渡すこともできます。

```python
from rhinestone import SearchQuery

results = app.search(SearchQuery(bbox=(139.5, 35.5, 140.0, 36.0), limit=10))
```

## Resultを選んで解決する

```python
result = results[0]
resource = app.resolve(result)

print(result.title)
print(result.metadata)
print(resource.uri)
```

`Result`は検索中だけ使う一時的な値です。Provider固有の対象指定はResultに保持されますが、endpointやCredentialは複製されません。

Providerごとのグループが必要な場合は、`results.items()`、`results.keys()`、`results["provider-id"]`を使えます。

## 検索条件

構成した全Providerが指定条件を扱える必要があります。対応しない条件がある場合は`UnsupportedSearchConditionError`になります。

検索結果は`app.resolve(result)`で直接Resourceへ解決できます。`result.to_config()`は内部パイプラインを調査する高度なAPIです。