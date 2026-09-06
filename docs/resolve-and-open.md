# Resource を解決して開く

Rhinestone の処理は二段階です。まず `resolve()` が provider の情報から `Resource` を
決定し、次に `open()` が登録済み runtime へ渡します。データを開かずに URI、metadata、
Provenance だけを使うこともできます。

## 1. Config を解決する

```python
from rhinestone import Config

resource = app.resolve(
    Config(
        source_id="direct",
        settings={
            "uri": "https://example.invalid/boundaries.geojson",
            "format": "geojson",
            "media_type": "application/geo+json",
        },
    )
)
```

解決後は、次の情報を確認できます。

```python
print(resource.uri)                   # 開く対象の URI
print(resource.format)                # 例: geojson, cog, shapefile
print(resource.media_type)            # provider が示した media type
print(resource.metadata)              # title、license、publisher など
print(resource.provenance)            # provider、元 URL、API endpoint など
print(resource.access_plan)           # file / service-query などのアクセス方法
```

`ConfigValidationError` は Config の値が不足・不正なとき、`AmbiguousResourceError` は
候補を一意に選べないときに発生します。推測に頼らず、resource ID、format、archive
entry point などを明示してください。

## 2. Runtime で開く

Rasterio を登録した COG/GeoTIFF Resource は、次のように開きます。

```python
with resource.open(adapter="rasterio") as dataset:
    print(dataset.width, dataset.height)
```

`adapter` を省略すると、互換性のある登録済み Adapter が自動選択されます。複数の
runtime を登録して再現性を保ちたい場合は、名前を指定してください。

```python
dataset = resource.open(adapter="gdal")
```

対応する runtime が未登録、または format が非対応の場合は
`ExecutionAdapterUnavailableError` になります。対応組み合わせは
[対応状況](compatibility.md)で確認してください。

## 3. 一度に実行する

中間の Resource が不要なら、`app.open(config, adapter=...)` を使えます。

```python
dataset = app.open(config, adapter="gdal")
```

ただし、license、配布元、選ばれた URI を記録したいときは、先に `resolve()` して
`Resource` を保存・確認する方法を推奨します。

## 典型的な失敗

| 状況 | 確認すること |
| --- | --- |
| `UnsupportedSourceError` | `source_id`に対応するproviderが構成されているか |
| `ConfigValidationError` | 必須設定、format、entry point、credential 名が正しいか |
| `ProviderMetadataError` | API endpoint、ネットワーク、認証情報を確認する |
| `ExecutionAdapterUnavailableError` | dependency 名と対応 format を確認する |
| `DependencyUnavailableError` | `dependencies` に runtime factory があるか、factory が import に成功するか |

より具体的な provider の設定は [Source Adapter 一覧](api/source-adapters.md) を参照してください。
