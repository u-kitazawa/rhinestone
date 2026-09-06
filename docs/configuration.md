# アプリケーションを構成する

Rhinestoneは`configure()`で作成した`app`を入口に使います。利用者はAdapterを
登録せず、名前付きproviderと、使用を許可する外部dependencyだけを宣言します。

## 最小構成

既知のURIを解決する`direct` providerは常に利用できます。

```python
from rhinestone import Config, configure

app = configure()
resource = app.resolve(
    Config(
        source_id="direct",
        settings={
            "uri": "https://example.invalid/data.geojson",
            "format": "geojson",
            "media_type": "application/geo+json",
        },
    )
)
```

## providerを構成する

`ProviderConfig`は一つのproviderを組み込みAdapter種別へ対応付けます。mappingの
keyがConfigや検索結果から参照する`source_id`です。

```python
from rhinestone import ProviderConfig, configure

app = configure(
    providers={
        "gspace": ProviderConfig(
            adapter_type="ckan",
            settings={"endpoint": "https://www.geospatial.jp/ckan"},
        ),
    },
    dependencies={"http-json": lambda: get_json},
)
```

`http-json` factoryは`get_json(url, params)`互換callbackを返します。認証headerを
使うproviderでは`get_json(url, params, headers)`も受け取れるようにします。
factoryは最初のrequestまで評価されません。

### 同じAdapter種別を複数利用する

provider idとAdapter種別は独立しています。

```python
app = configure(
    providers={
        "national": ProviderConfig(
            "ckan", {"endpoint": "https://national.example/api"}
        ),
        "municipal": ProviderConfig(
            "ckan", {"endpoint": "https://city.example/api"}
        ),
    },
    dependencies={"http-json": lambda: get_json},
)
```

検索結果は`national`と`municipal`に分かれ、`to_config()`後も同じsource idを
保持します。

## データを開くdependency

組み込みExecution AdapterはRhinestoneが構成します。利用者はruntime factoryだけを
渡します。

```python
import rasterio

app = configure(
    dependencies={"rasterio": lambda: rasterio},
)
```

`resource.open()`時に、Resourceと登録済みdependencyに対応するAdapterが自動選択
されます。再現性のために固定する場合だけ`resource.open(adapter="rasterio")`を
指定します。

## dependency名

| 名前 | factoryが返すもの | 用途 |
| --- | --- | --- |
| `http-json` | JSON取得callback | CKAN、STAC、e-Stat、OGC等 |
| `http-text` | text取得callback | DCAT文書 |
| `rdflib` | RDFLib互換module | DCAT解釈 |
| `gdal` | GDAL互換module | GISデータを開く |
| `rasterio` | Rasterio互換module | rasterを開く |
| `pyogrio` | pyogrio互換module | vectorを開く |
| `json-service` | requests互換runtime | ODPT等 |

## secretを渡す

ODPT等の実行時secretはlogical nameに対応するfactoryとして登録します。

```python
app = configure(
    providers={"odpt": ProviderConfig("odpt")},
    dependencies={"json-service": lambda: requests},
    credentials={"odpt": lambda: os.environ["ODPT_CONSUMER_KEY"]},
)
```

secretをConfig、Metadata、Provenanceへ保存しないでください。

次は[データを検索する](search.md)または
[Resourceを解決して開く](resolve-and-open.md)へ進んでください。

