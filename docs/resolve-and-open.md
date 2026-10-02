# Resourceを解決して開く

Rhinestoneの通常フローは`Result -> Resource -> Data`です。

## ResultをResourceへ解決する

```python
result = app.search(text="河川")[0]
resource = app.resolve(result)
```

`Resource`にはURIだけでなく、format、metadata、provenance、アクセス方法が含まれます。検索結果を解決するためにConfigを組み立てる必要はありません。

Sourceによってはprovider metadataを解釈するためのSource Runtimeが検索・解決時に
必要です。たとえばDCATは`rdflib`を`search()`または`resolve()`で遅延評価します。
解決済みResourceとAccessPlanはSource Runtimeの実体やfactoryを保持しません。

## Runtimeで開く

開くRuntimeを明示します。

```python
import rasterio

app = configure(
    catalog=BUILTIN,
)
resource = app.resolve(result)
with resource.open("rasterio", runtime=rasterio) as dataset:
    ...
```

またはアプリケーションに解決とopenをまとめて依頼できます。

```python
dataset = app.open(result, "rasterio", runtime=rasterio)
```

RhinestoneはGIS I/O、形式変換、空間演算、解析を行いません。選択済みResourceを利用者が所有するRuntimeへ渡します。
Execution Runtimeは`configure()`に登録せず、`open()`の呼び出しごとに渡します。

Adapter名（`gdal`、`rasterio`、`pyogrio`など）は必須です。指定したAdapterがResourceに
対応しない場合やRuntime実体がない場合は`ExecutionAdapterUnavailableError`になります。
Execution Runtimeへ`RuntimeFactory`を渡すこともできません。
ODPTのJSONサービスはCoreが通信するため、`resource.open("json-service")`とし、
`runtime=`を省略します。

## 高度な直接解決

Provider固有の対象指定を再現可能なConfigとして扱う必要がある場合だけ、`Config`を使います。

```python
resource = app.resolve(Config(
    source_id="direct",
    settings={
        "uri": "https://example.invalid/data.geojson",
        "format": "geojson",
        "media_type": "application/geo+json",
    },
))
```
