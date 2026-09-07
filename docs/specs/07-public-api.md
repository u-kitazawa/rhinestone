# 利用インターフェース

## 基本境界

公開 API は、名前付き Source の構成、Config から Resource を解決する経路、Resource を外部 OSS へ接続する経路、SearchQuery から SearchResult を得る経路を提供します。

利用者は Source Adapter または Execution Adapter の instance を登録しません（MUST NOT）。Rhinestone が `SourceDefinition` と dependency から組み込み Adapter を構成・選択します。HTTP transport はRhinestoneが組み込みで提供します。

```python
from rhinestone import Config, configure, sources

app = configure(
    sources=(sources.GEOSPATIAL_JP,),
    dependencies={
        "gdal": lambda: osgeo.gdal,
    },
)
resource = app.resolve(
    Config(source_id="geospatial-jp", settings={"resource_id": "..."})
)
```

Catalog の `sources.json` が接続先を持ち、`sources.py` は読み込んだ `SourceDefinition` を便利な名前で公開します。`Config` は対象指定だけを保持します。

独自の Source を構成する場合は `SourceDefinition` を明示します。

```python
from rhinestone import SourceDefinition, configure

app = configure(
    sources=(
        SourceDefinition(
            id="my-stac",
            adapter_type="stac",
            settings={"endpoint": "https://stac.example/api"},
        ),
    ),
)
```

同じ `adapter_type` を異なる `source_id` へ割り当てられます（MUST）。未知の adapter type、空の source id、未知の Source option は明示的に失敗します。

`direct` Source は常に組み込まれます。利用者が上書きすることはできません。

## 公開モデル

### v0.5のDiscovery / Resolution semantics

`SearchResult.to_config()` は解決先のtarget Configを返します。発見元Sourceと解決先Sourceは異なってよく、横断catalog側のprovenanceと元provider側のprovenanceを失わないようにします。

`SourceDefinition` は Catalog から読み込まれた静的な構成、`Config` は選択した Source 内の対象、`Source` は Adapter が外部情報を解釈した実行時の結果です。これらを同じ「source情報」として混同しません。

`SearchResult.to_config()` は同じ source id を保持して通常の解決フローへ戻します。`Provenance.provider` には source id、`Provenance.adapter` には Adapter 種別を記録します。

Resource は少なくとも次へ直接アクセスできます。

```python
resource.uri
resource.metadata
resource.provenance
resource.access_plan
```

## runtime dependency

利用者はRhinestoneが実装しない外部 runtime を 実体またはfactoryとして供給します。組み込み Execution Adapter はRhinestone側で構成され、登録済みdependencyとの互換性から選択されます。Core が GDAL 等を直接 import してはなりません（MUST NOT）。

Source metadataのJSON取得、DCAT文書取得、JSON serviceのHTTP通信はRhinestoneの組み込みtransportを使用します（MUST）。利用者にHTTP callbackまたはrequests互換runtimeの登録を要求してはなりません（MUST NOT）。`rdflib` は DCAT 解釈 runtime、GIS 実行には `gdal`、`rasterio`、`pyogrio` を使用します。外部runtime factoryは実際に必要になるまで評価しません。

```python
resource.open("gdal")
```

`configure()` は process-global state を変更せず、独立した application context を返します。同じ process 内に異なる Source・dependency 構成を共存させられます。

## credential

`credentials` は logical name と secret factory の対応です。secret を Catalog、SourceDefinition、Config、Source、Metadata、Provenance へ保存してはなりません（MUST NOT）。Source API 認証の評価時点と統一方法は別途 credential 契約で定義します。

## 戻り値

Rhinestone は結果を共通 DataFrame や独自形式へ変換しません。Execution Adapter は外部 OSS のデータ型と処理契約を尊重します。利用者は Resource を実行せず、URI、Metadata、Provenance だけを利用することもできます。
