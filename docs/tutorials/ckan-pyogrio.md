# CKANのベクター配布物をpyogrioで読む

CKANの一つのdatasetには複数のdistribution（CKAN APIでは `resource`）が含まれます。
この例では、G空間情報センターの検索結果から直接読めるベクター配布物を明示的に選び、
pyogrioへ渡します。

## 準備

```console
python -m pip install rhinestone pyogrio geopandas
export RHINESTONE_CKAN_QUERY="河川"
export RHINESTONE_CKAN_RESULT_INDEX="0"
```

G空間情報センターの公開CKAN APIへ接続するため、ネットワーク接続が必要です。検索結果から、
GeoJSON、GeoPackage、またはFlatGeobufとして提供されているdistributionを選べる検索語を
指定してください。ZIP archiveしかないdistributionは、このpyogrioの例では選択しません。

## 検索、distribution選択、pyogrioへの受け渡し

```python
import os
from collections.abc import Mapping
from typing import Any, Optional

import pyogrio

from rhinestone import configure, sources


def vector_format(result: Any) -> Optional[str]:
    """Read the format advertised by the selected CKAN resource."""
    resources = result.metadata.raw.get("resources", [])
    resource_id = result.provenance.resource_identifier
    if not isinstance(resources, (list, tuple)) or not isinstance(resource_id, str):
        return None
    for resource in resources:
        if not isinstance(resource, Mapping) or resource.get("id") != resource_id:
            continue
        format_name = resource.get("format")
        if not isinstance(format_name, str):
            return None
        normalized = format_name.lower()
        return {"geopackage": "gpkg"}.get(normalized, normalized)
    return None


app = configure(sources=(sources.GEOSPATIAL_JP,))
results = app.search(
    text=os.environ.get("RHINESTONE_CKAN_QUERY", "河川"),
    limit=20,
)
supported = [
    result
    for result in results
    if vector_format(result) in {"geojson", "gpkg", "flatgeobuf"}
]
if not supported:
    raise RuntimeError("The CKAN search returned no direct vector distribution")

for index, result in enumerate(supported):
    print(f"[{index}] {result.title}")
    print("    resource id:", result.provenance.resource_identifier)
    print("    format:", vector_format(result))

selected = supported[
    int(os.environ.get("RHINESTONE_CKAN_RESULT_INDEX", "0"))
]
resource = app.resolve(selected)
frame = resource.open("pyogrio")

print("resource:", resource.uri)
print("format:", resource.format)
print("rows:", len(frame))
print("columns:", list(frame.columns))
```

CKANのpackage検索はdataset単位の結果をdistributionごとに展開します。`Result`の
provenanceにあるresource IDと検索metadata内の `resources` を照合して、providerが広告した
形式だけを選んでいます。その後の `app.resolve(selected)`で配布URLを取得し、
`resource.open("pyogrio")`が選択済みURIをpyogrioへ渡します。

## この例の境界

- 必須: ネットワーク接続、G空間情報センターの公開CKAN API、pyogrio / GeoPandas
- credential: この公開CKANの標準経路では不要
- 変更される値: dataset、resource ID、配布URL、形式、公開状態
- Rhinestoneの責務: CKAN検索、dataset内のdistribution選択、公式配布URLの解決、pyogrioへの委譲
- pyogrio / GeoPandasの責務: ベクターデータの読み込みとDataFrame操作
- 非対応: HTMLページの解析、URLや形式の推測、ZIP archive URIの自動構築、空間演算

ZIP内のCityGMLなど、archive memberの指定とGDALが必要なケースは[PLATEAU Adapter](../api/adapters/plateau.md)
と[GDALのRuntime説明](../runtimes.md)を参照してください。CKANの対応範囲は
[CKAN Adapter](../api/adapters/ckan.md)にも記載しています。
