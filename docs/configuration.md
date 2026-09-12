# アプリケーションを構成する

Rhinestoneのアプリケーションは、使うデータ提供元、必要な外部ライブラリ、認証情報を組み合わせて作ります。
最初は組み込みCatalogだけで構成し、必要になったときにRuntimeやCredentialを追加してください。

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

## 独自の提供元を追加する

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

`Provider`の`adapter_type`や`settings`は接続方法を指定する構成情報です。通常は組み込みCatalogのProviderを使います。

## 独自 Adapter を追加する

詳しい実装手順、Context、検索、エラー処理は[Custom Adapter を作る](custom-adapters.md)を参照してください。

Source と Execution は、組み込みと同じパイプラインへ明示的に登録できます。

```python
from rhinestone import Catalog, Provider, configure
from rhinestone.adapters.contracts import (
    ExecutionAdapterDefinition,
    SourceAdapterDefinition,
)

catalog = Catalog((Provider("example", "example-source"),))

class ExampleSource:
    def load(self, config):
        ...  # Source を返す

class ExampleExecution:
    name = "example-runtime"
    priority = 100
    def supports(self, resource, dependencies): ...
    def open(self, resource, runtime, *, destination_policy=None): ...

app = configure(
    catalog=catalog,
    adapters=(
        SourceAdapterDefinition(
            "example-source",
            lambda provider, context: ExampleSource(),
        ),
        ExecutionAdapterDefinition(
            "example-runtime",
            lambda context: ExampleExecution(),
        ),
    ),
    dependencies={"example-runtime": example_runtime},
)
```

Source factoryには、組み込みHTTP transport、Credential、依存Runtime、DestinationPolicyを
`SourceAdapterContext`として渡します。Execution factoryには`ExecutionAdapterContext`を渡します。

共有知識をSource Adapterへ疎結合に注入できます。標準のTime Adapterは自動登録されるため、
追加設定なしで西暦・年度・元号を利用できます。自治体辞書など独自の公式データを使う場合は、
`adapters`へ`KnowledgeAdapterDefinition`を渡します。独自定義は同じ種別の標準実装を置き換えます。

```python
from rhinestone import configure
from rhinestone.adapters.knowledge import KnowledgeAdapterDefinition, StandardTimeAdapter

app = configure(
    adapters=(
        KnowledgeAdapterDefinition(
            "official-municipality", make_municipality_adapter, "identity"
        ),
    )
)
```

Knowledge Adapter factoryにはSource/Execution Adapterと同じくContextが渡されます。Source Adapter Contextの`knowledge`から必要なadapterだけを取得します。Knowledge Adapterは
Metadata/Provenanceやcanonical valueを扱いますが、Credential、Runtime、データ処理は保持しません。
同じ`adapter_type`またはExecution名を複数登録することはできません。

## 外部ライブラリ（Runtime）

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

from rhinestone import configure
from rhinestone.models import RuntimeFactory

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

## 認証情報（Credential）

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

`network_policy` は `credentialed`（既定）または `none` から選べます。`credentialed`
は認証付き通信だけを、CatalogでProviderごとに定義された実行endpointへ制限します。
説明・仕様・利用条件等のmetadata URLや別ProviderのendpointはCredential送信先になりません。
ODPTでは`endpoint + resource_types`だけが対象です。`none`では宛先制限を行いません。

Adapterを直接構築する既存コードでは、明示的に作成した`DestinationPolicy(rules=...)`の
ruleをCredential付き通信にも引き続き利用できます。`from_catalog()`で生成したpolicyは、
Providerの実行endpointからCredential専用ruleを生成します。Catalogに論理Credential名を
持たないProviderでも、直接指定した`api_token`／`api_key`はその実行endpointだけへ送信できます。

## 高度なAPI

`Config`、Source Adapter、Resolver、AccessPlanは内部パイプラインを直接扱う高度なAPIです。通常の検索・解決では`Result`を`app.resolve()`へ渡してください。
