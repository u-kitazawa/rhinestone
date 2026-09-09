# データを検索する

`app.search()`は構成済みProviderを横断してResultを返します。検索したSourceと、結果を解決するSourceは同一である必要はありません。

## 文字列と検索パラメータ

```python
results = app.search(text="人口", limit=10)
```

`text`、`bbox`、`time`、`limit`をキーワードで指定できます。高度な用途では`SearchQuery`を渡すこともできます。

- `text`: `str`または`None`
- `limit`: `bool`を除く0以上の整数
- `bbox`: 数値4要素のtuple
- `time`: `datetime`または`None`を2要素で保持するtuple

不正な値はProviderへリクエストする前に`ConfigValidationError`になります。

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

Resultは次の情報を持ちます。

- `discovered_by`: 結果を発見したSource ID
- `target`: `app.resolve()`へ渡す解決先の`Config`
- `metadata` / `provenance`: 発見時に得られた知識

横断CKAN検索の結果は、`discovered_by="search-ckan-jp"`、`target.source_id="direct"` のようになります。`target`は`result.to_config()`で取得できます。解決先が発見元と異なる場合も、発見元のmetadataとprovenanceはResourceへ引き継がれます。

## 結果の順序

単一Providerでは、iterationと整数indexingはProviderが返した順序をそのまま使います。
複数Providerでは、`catalog`または`sources`へ構成したProvider順にgroupを連結し、
各group内ではProviderが返した順序を保ちます。したがって`results[0]`は最初に構成した
Providerの先頭結果であり、Providerを横断した「最も関連度が高い結果」ではありません。

Rhinestoneは共通scoreやrerankerを持たないため、異なるProviderのrankingを比較しません。
Source IDの辞書順もrankingには使われず、Source IDをrenameしても構成位置が同じなら
iteration順は変わりません。Provider固有のrankingを扱う場合は、
`results.items()`、`results.keys()`、`results["provider-id"]`でgroupごとに参照してください。

## 検索条件

各Sourceは対応する条件だけを受け取ります。例えば`text`に対応するCKANと`bbox`に対応するSTACを構成している場合、両方を指定しても検索全体は失敗せず、各Sourceへ理解できる条件だけが渡されます。

適用されなかった条件は`results.diagnostics`で確認できます。

```python
for diagnostic in results.diagnostics:
    print(
        diagnostic.source_id,
        diagnostic.reason,
        diagnostic.skipped_conditions,
        diagnostic.missing_conditions,
    )
```

指定条件とSourceの対応が一つもないSourceは、空の検索を実行せずスキップします。Sourceに必須条件がある場合、その条件が指定されていないSourceも検索せずスキップします。`diagnostic.reason`は通常`unsupported`または`missing_required`で、後者では`missing_conditions`に不足条件が入ります。

検索結果は`app.resolve(result)`で直接Resourceへ解決できます。`app.search()`が返したResultでは
`result.resolve()`も同じResourceを返し、発見元と解決先が異なる場合もmetadataとprovenanceを
保持します。`result.to_config()`は内部パイプラインを調査する高度なAPIです。
