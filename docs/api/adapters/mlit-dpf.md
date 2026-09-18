# MlitDpfAdapter（国交DPF検索アダプター）

`MlitDpfAdapter` は国土交通データプラットフォーム（DPF）のGraphQL APIを検索・発見元として
利用するDiscovery専用Sourceです。

[Source Adapter 一覧](../source-adapters.md) · source type: `mlit-dpf`

## 構成

組み込み定義 `sources.MLIT_DPF` はendpointと論理Credential名だけを持ちます。APIキーは
`credentials` から遅延取得され、`Provider`、`Result`、`Resource`、例外には保存されません。

```python
from rhinestone import Provider, configure

dpf = Provider(
    "dpf",
    "mlit-dpf",
    {
        "endpoint": "https://data-platform.mlit.go.jp/api/v1",
        "credential": "mlit-dpf",
        "target_rules": [
            {
                "catalog_id": "official-catalog-id",
                "dataset_id": "official-dataset-id",
                "source_id": "plateau",
                "settings": {
                    "dataset_id": {"metadata": "provider:dataset_id"},
                    "resource_id": {"metadata": "provider:resource_id"},
                },
            }
        ],
        "representations": {
            "fallback-dataset-id": {
                "format": "gpkg",
                "media_type": "application/geopackage+sqlite3",
            }
        },
    },
)

app = configure(
    sources=(dpf, Provider("plateau", "plateau", {"endpoint": "https://example.test/ckan"})),
    credentials={"mlit-dpf": lambda: load_api_key()},
    dependencies={"pyogrio": pyogrio},
)
```

`target_rules` の各規則は `catalog_id`、任意の `dataset_id`、委譲先の登録済み
`Provider.id`、target Configの各設定値を取得する `record` または `metadata` selectorを
宣言します。委譲先はConfigを解決できるネイティブSourceでなければなりません。`direct` と
Discovery専用の別 `mlit-dpf` Providerは委譲先に指定できず、構成時に
`ConfigValidationError` になります。dataset固有規則がcatalog規則より優先され、同じ
組み合わせの重複は拒否されます。URL、タイトル、catalog名から提供元やIDを推測しません。

ネイティブ委譲に必要な値がない場合だけ、`representations` にdatasetの形式があり、かつ
metadataに安全な `DPF:downloadURLs` がある結果を `direct` Configへ変換します。
`DPF:dataURLs` はランディングページなのでResource URIには使いません。download URLのschemeは
大文字小文字を区別せずHTTPまたはHTTPSとして検証し、埋め込みCredentialや不正なauthorityを
拒否します。

## 検索と実行

`text`、WGS84の `bbox=(west, south, east, north)`、`limit` に対応します。`time` は未対応として
検索diagnosticに記録されます。`limit=None` のDPF取得上限は50件、`limit=0` は通信しません。

```python
results = app.search(text="道路", bbox=(139.5, 35.5, 140.0, 36.0), limit=10)
result = results[0]
resource = app.resolve(result)
data = resource.open("pyogrio")
```

DPFは発見元であり、実行Runtimeを選びません。ネイティブ委譲でもDirect fallbackでも、利用者が
`app.open(result, "gdal")`、`resource.open("pyogrio")` などでRuntimeを明示します。指定した
RuntimeがResource形式と非互換なら、別のRuntimeへ暗黙に切り替えず
`ExecutionAdapterUnavailableError` になります。

署名付き `fileDownloadURLs`、半径・属性検索、互換Runtime一覧APIは対象外です。
