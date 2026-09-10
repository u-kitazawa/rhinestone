# アプリケーションを構成する

アプリケーションはCatalog、Runtime、Credentialを組み合わせて作ります。

## Catalogを指定する

```python
from rhinestone import configure
from rhinestone.catalogs import BUILTIN

app = configure(catalog=BUILTIN)
```

組み込みCatalogからProviderを限定する場合は、新しいCatalogを作ります。

```python
from rhinestone import Catalog, configure
from rhinestone.catalogs import BUILTIN

app = configure(catalog=Catalog((
    BUILTIN.providers[0],
    BUILTIN.providers[2],
)))
```

## 独自Providerを追加する

```python
from rhinestone import Catalog, Provider, configure

catalog = Catalog((
    Provider(
        id="my-stac",
        adapter_type="stac",
        settings={"endpoint": "https://stac.example/api"},
    ),
))
app = configure(catalog=catalog)
```

`Provider`の`adapter_type`や`settings`は拡張向けの構成情報です。通常は組み込みCatalogのProviderを使います。

## Runtime

外部Runtimeは利用者が所有し、実体または明示的な `RuntimeFactory` として渡します。
公開APIではどちらも単一の`dependencies`引数へ渡しますが、内部では利用段階に応じて
Source RuntimeとExecution Runtimeへ分離されます。

```python
app = configure(
    catalog=BUILTIN,
    dependencies={
        "gdal": gdal,
        "rasterio": rasterio,
        "pyogrio": pyogrio,
        "rdflib": rdflib,
    },
)
```

HTTP JSON、HTTP text、JSON serviceのRuntimeは組み込みです。

遅延評価が必要な場合は、factoryを `RuntimeFactory` で包みます。bare valueはcallableでも
Runtime実体として扱われるため、callable façadeやMockがfactoryとして誤実行されません。

```python
import importlib

from rhinestone import RuntimeFactory, configure

app = configure(
    dependencies={
        "rasterio": RuntimeFactory(lambda: importlib.import_module("rasterio")),
    },
)
```

| 種類 | 用途 | factoryの評価時点 | 例 |
| --- | --- | --- | --- |
| Source Runtime | provider / protocol metadataの解釈 | 対象Sourceの`search()`または`resolve()`で初めて必要になった時 | `rdflib` |
| Execution Runtime | 解決済みResourceを開く | `Resource.open()`で初めて必要になった時 | `gdal`、`rasterio`、`pyogrio` |

`configure()`は `RuntimeFactory` を評価しません。Source Runtimeは解決済みResourceや
AccessPlanへ保持されず、Execution RuntimeだけがResourceのopen経路から参照されます。

## Credential

secretはCatalogやProviderに保存せず、Credential factoryとして渡します。

```python
app = configure(
    catalog=BUILTIN,
    credentials={
        "odpt": lambda: os.environ["ODPT_CONSUMER_KEY"],
    },
)
```

認証付き CKAN、STAC、OGC Source は、Provider に secret ではなく Credential の論理名を
指定します。

```python
catalog = Catalog((Provider(
    id="private-stac",
    adapter_type="stac",
    settings={
        "endpoint": "https://stac.example/api",
        "credential": "stac-token",
    },
),))
app = configure(
    catalog=catalog,
    credentials={"stac-token": lambda: os.environ["STAC_TOKEN"]},
)
```

`network_policy` は `credentialed`（既定）、`strict`、`none` から選べます。`credentialed`
は認証付き通信だけを Catalog endpoint に制限し、`strict` は ExecutionAdapter の HTTP
アクセス全体を制限します。GDAL系Runtimeへ渡す `/vsicurl/`、
`/vsicurl_streaming/`、archive wrapperとの組み合わせでは内側のHTTP(S) URLを認可し、
認識できない `/vsi.../` locatorはローカルpathと推測せず拒否します。認可されない宛先では
Credential factoryやExecution Runtimeは評価・呼び出しされません。

## 高度なAPI

`Config`、Source Adapter、Resolver、AccessPlanは内部パイプラインを直接扱う高度なAPIです。通常の検索・解決では`Result`を`app.resolve()`へ渡してください。
