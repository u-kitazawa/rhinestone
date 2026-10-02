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
Rhinestone の representation registry で `vector` と明示された形式として提供されている
distributionを選べる検索語を指定してください。ZIP Shapefile を選ぶ場合も、
`archive="zip"`（必要なら ZIP 内の `entry_point`）が Source で明示されていれば同じ例で開けます。

## 検索、distribution選択、pyogrioへの受け渡し

```python
from rhinestone.catalogs import BUILTIN
from rhinestone.catalogs import Catalog
import os

import pyogrio

from rhinestone import FormatPreset, configure

app = configure(
    catalog=Catalog(provider for provider in BUILTIN if provider.id == "geospatial-jp"),
)
results = app.search(
    text=os.environ.get("RHINESTONE_CKAN_QUERY", "河川"),
    format=(FormatPreset.PYOGRIO,),
    limit=20,
)
if not results:
    for diagnostic in results.diagnostics:
        print(diagnostic.source_id, diagnostic.reason, diagnostic.failure_type)
    raise RuntimeError("The CKAN search returned no direct vector distribution")

for index, result in enumerate(results):
    print(f"[{index}] {result.title}")
    print("    resource id:", result.provenance.resource_identifier)
    print("    formats:", sorted(result.formats))

selected = results[int(os.environ.get("RHINESTONE_CKAN_RESULT_INDEX", "0"))]
resource = app.resolve(selected)
frame = resource.open("pyogrio", runtime=pyogrio)

print("resource:", resource.uri)
print("format:", resource.format)
print("rows:", len(frame))
print("columns:", list(frame.columns))
```

CKANのpackage検索はdataset単位の結果をdistributionごとに展開します。
`FormatPreset.PYOGRIO`で、対象Resourceが宣言するベクター形式だけを選びます。
raw metadataを利用者側で解釈したり、別Resourceの形式を流用したりする必要はありません。
CKAN Adapterは形式照合後の結果に`limit=20`を適用し、必要なら次のpackage pageを取得します。
`Result.formats`で検索時の形式を確認できます。その後の `app.resolve(selected)`で配布URLを取得し、
`resource.open("pyogrio", runtime=pyogrio)`が選択済みURIをpyogrioへ渡します。ZIP の場合は、選択済みの
`archive` と任意の `entry_point` から GDAL VSI URI を組み立てます。
利用者が所有する実体は`resource.open("pyogrio", runtime=pyogrio)`へ明示的に渡します。導入方法と
責任境界は[pyogrio Runtime](../runtimes.md#pyogrio)を参照してください。
選択できても、利用者のpyogrio/GDAL環境に対応 read driver がない場合や、geometry / field typeを
読めない場合は `ResourceAccessError` になります。

## この例の境界

- 必須: ネットワーク接続、G空間情報センターの公開CKAN API、pyogrio / GeoPandasのインストールと`open()`へのpyogrio実体の指定
- credential: この公開CKANの標準経路では不要
- 変更される値: dataset、resource ID、配布URL、形式、公開状態
- Rhinestoneの責務: CKAN検索、dataset内のdistribution選択、公式配布URLの解決、pyogrioへの委譲
- pyogrio / GeoPandasの責務: ベクターデータの読み込みとDataFrame操作
- 非対応: HTMLページの解析、URL・形式・ZIP memberの推測、空間演算

ZIP内のCityGMLなど、archive memberの指定とGDALが必要なケースは[PLATEAU Adapter](../api/adapters/plateau.md)
と[GDALのRuntime説明](../runtimes.md)を参照してください。CKANの対応範囲は
[CKAN Adapter](../api/adapters/ckan.md)にも記載しています。
