# Rhinestone documentation

Rhinestoneは、日本の公的・地理空間データを**検索し、Resourceへ解決し、既存ライブラリで利用するためのPythonライブラリ**です。

データ提供元ごとの検索API、識別子、配布形式、アクセス方法をRhinestoneがSpecとして保持し、利用者は共通の流れで扱います。

```text
検索 → 選択 → Config → Resourceの解決 → データを開く
```

## まずはSourceを選ぶ

```python
from rhinestone import configure, sources

app = configure(
    sources=sources.ALL,
)
```

通常ユーザーはAdapterやendpointを組み立てません。必要なSourceだけに絞ることもできます。

```python
app = configure(
    sources=(sources.GEOSPATIAL_JP, sources.PLATEAU),
)
```

## 検索からResourceへ

```python
from rhinestone import SearchQuery

results = app.search(SearchQuery(text="河川", limit=5))
result = results["geospatial-jp"][0]
config = result.to_config()
resource = app.resolve(config)

print(resource.uri)
print(resource.format)
print(resource.metadata)
print(resource.provenance)
```

`SearchResult`はSourceのendpointを複製せず、`source_id`と対象固有の`settings`だけをConfigへ渡します。

## 既存ライブラリで開く

Rhinestone自身はGIS I/O・変換・解析を再実装しません。GDAL、Rasterio、pyogrio等は利用者がruntime dependencyとして供給します。

```python
app = configure(
    sources=sources.ALL,
    dependencies={
        "http-json": lambda: get_json,
        "rasterio": lambda: rasterio,
    },
)

with resource.open(adapter="rasterio") as dataset:
    ...
```

## Source / Config / Adapter の境界

- `SourceDefinition`: どのデータ提供元を使うか
- `Config`: そのSource内で何を使うか
- Source Adapter: 接続・解決方法の知識
- dependency: HTTP、GDAL、Rasterio、SDK等のruntime
- credential: secret

`SourceDefinition`、`Source`、`Resource`などの違いは[用語と概念](concepts.md)でまとめています。

`direct`はexternal SourceではなくCore機能なので、`sources.ALL`と無関係に常時利用できます。

## 次に読む

- [Getting started](getting-started.md)
- [用語と概念](concepts.md)
- [アプリケーションを構成する](configuration.md)
- [データを検索する](search.md)
- [Resourceを解決して開く](resolve-and-open.md)
- [対応状況](compatibility.md)
- [APIリファレンス](api.md)
