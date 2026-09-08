# PLATEAUのCityGMLを探してGDALで開く

G空間情報センターのCKAN検索でPLATEAUの配布物を探し、選んだResourceとZIP内のCityGMLメンバーを明示してGDALへ渡します。これはdistribution / archive型の例です。

## 必要なもの

- RhinestoneとPython 3.10以上
- GDALのPython bindingsと利用可能なnative GDAL
- G空間情報センターへのnetwork access
- 利用条件を確認済みのPLATEAU配布物と、ZIP内の相対CityGMLパス

GDALはOSやnative libraryの組み合わせに依存するため、[GDALのPython bindings guide](https://gdal.org/en/stable/api/python_bindings.html)を優先してください。Rhinestoneの対応形式や導入上の注意は[Runtimeの導入ガイド](../runtimes.md)にあります。

```console
python -m pip install rhinestone
export RHINESTONE_PLATEAU_RESULT_INDEX="0"
export RHINESTONE_PLATEAU_CITYGML_MEMBER="udx/bldg/533946_building_lod2.gml"
```

## 配布物を検索して選ぶ

```python
import os

from osgeo import gdal

from rhinestone import Config, configure, sources

app = configure(
    sources=(sources.PLATEAU,),
    dependencies={"gdal": gdal},
)

results = app.search(text="横浜市", limit=10)
if not results:
    raise RuntimeError("PLATEAUの検索結果がありません")

for index, result in enumerate(results):
    print(f"[{index}] {result.title} ({result.provenance.resource_identifier})")

selected = results[int(os.environ["RHINESTONE_PLATEAU_RESULT_INDEX"])]
selected_config = selected.to_config()
```

検索結果のResource IDだけでは、ZIP内のどのファイルを開くかは決まりません。検索結果を確認し、対象の配布物がCityGMLを含む公式ZIPであることと、相対`entry_point`を利用者が確認します。

## ZIP内のCityGMLを明示して開く

```python
resource = app.resolve(
    Config(
        source_id=selected_config.source_id,
        settings={
            **selected_config.settings,
            "archive": "zip",
            "entry_point": os.environ["RHINESTONE_PLATEAU_CITYGML_MEMBER"],
        },
    )
)

dataset = resource.open("gdal")
print("resource:", resource.uri)
print("provider:", resource.provenance.provider)
print("layer count:", dataset.GetLayerCount())
```

`entry_point`は安全な相対パスでなければならず、`..`や絶対パスは指定できません。Rhinestoneは自治体・年度からResourceやarchive memberを推測せず、GDAL用にZIP URIと明示されたmemberを組み立てます。CityGMLのレイヤー解釈や解析はGDALに委譲されます。

なお、検索結果がCityGML以外のResourceを指している場合、GDALで開けるとは限りません。配布物の形式、ファイルサイズ、利用条件、ZIP内のパスは、G空間情報センターとPLATEAUの公開情報で確認してください。

詳細は[PLATEAU Source Adapter](../api/adapters/plateau.md)、[GDAL](../runtimes.md#gdal)、[対応状況](../compatibility.md)を参照してください。
