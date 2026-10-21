# Custom Adapter を作る

Rhinestone の Adapter は、Provider 固有の情報を配信単位の `Resource` へ変換する Provider
Adapter と、選択済みの `AccessPlan` を外部 Runtime へ渡す Runtime Adapter に分かれます。
外部Provider Adapterは、インストールされたPython packageのEntry Pointsから発見できます。
Provider / Runtime / KnowledgeのDefinitionを `configure(adapters=...)` へ明示登録することもできます。組み込み Adapter も
「あらかじめ登録された Definition」として同じ Registry に追加されるため、Custom Adapter
と同じ Factory／Context／選択経路を通ります。process-globalな可変登録状態は持ちません。

構造的な契約は`rhinestone.adapters.contracts.ProviderAdapter`／`RuntimeAdapter`のProtocolです。
共通実装を継承する場合は`rhinestone.adapters.provider.ProviderAdapter`／
`rhinestone.adapters.runtime.RuntimeAdapter`の基底クラスを利用できます。継承は必須ではありません。

## インストール済みProvider Adapter

外部packageはDefinitionオブジェクトを1つexportし、Entry Point名と
`ProviderAdapterDefinition.adapter_type`を一致させます。export先はfactoryそのものではありません。

```toml
[project.entry-points."rhinestone.provider_adapters"]
example-source = "example_package:definition"
```

```python
# example_package/__init__.py
from rhinestone.adapters.contracts import ProviderAdapterDefinition
from .adapter import make_adapter

definition = ProviderAdapterDefinition("example-source", make_adapter)
```

利用側は通常のpip/uvでpackageをインストールし、Catalogで選択します。

```python
app = configure(catalog=Catalog((Provider("example", "example-source"),)))
```

`configure()`は `importlib.metadata.entry_points()` でmetadataだけを読み、
Catalogの `Provider.adapter_type` で選んだexportだけをloadします。未使用の外部Providerや
任意依存はimportしません。同じ種類を複数Providerへ使う場合、Definitionのloadは
アプリケーションごとに1回、factoryによるAdapter生成はProviderごとに行います。

Entry Point名の重複（外部同士・組み込み・明示登録との衝突）は選択前に
`AdapterDiscoveryError`で拒否します。選択時のimport失敗は `AdapterLoadError`、
export型・identity・factory結果のload契約不一致は `AdapterContractError`、
インストール済みfactoryの実行失敗は `AdapterFactoryError`です。
これらは `AdapterRegistrationError`の派生型です。診断にはdistribution / group / identityを
含め、import/factory例外の任意payloadは表示しません。欠落したProviderの選択には従来の
`AdapterRegistrationError`を返します。

Provider・Runtime・Knowledgeの3つのgroupを選択・生成へ接続しています。
組み込みの実装も選択したProvider、明示したRuntime、初めて利用するKnowledge種別だけを
読み込みます。公開packageの個別exportも明示import時に読み込みます。
Rhinestone独自のインストーラや依存解決、未信頼Pythonコードの隔離は提供しません。
選択したpackageは利用者のtrust boundary内で実行されます。

## インストール済みKnowledge Adapter

`KnowledgeAdapterDefinition`をexportし、Entry Point名と`adapter_type`を一致させます。

```toml
[project.entry-points."rhinestone.knowledge_adapters"]
example-time = "example_package.knowledge:definition"
```

利用側は`configure(knowledge={"time": "example-time"})`のように種別ごとに選択します。
種別は`area`、`identity`、`time`です。既定のarea/timeは組み込みを使い、identityは未選択です。
同種別の候補を複数インストール・明示登録しても自動的には置き換えません。
重複identityはmetadataで検査し、選択されたexportだけをconfigure時にloadして
Definitionの型・identity・kindを検証します。factoryはその種別の最初の利用時に評価され、
アプリケーションごとにキャッシュされます。依存は宣言された範囲だけContextへ渡します。
インストール済みfactoryの失敗は`AdapterFactoryError`、種別に必要なmethodの欠落は
`AdapterContractError`となり、診断にはdistribution / group / identityを含めます。
解決結果のcanonical値の検証は既存のKnowledge契約に従います。

## インストール済みRuntime Adapter

次のgroupでは `RuntimeAdapterDefinition` オブジェクトをexportします。
Entry Point名とDefinitionの `name` を一致させます。

```toml
[project.entry-points."rhinestone.runtime_adapters"]
example-runtime = "example_package.runtime:definition"
```

`configure()`では名前の重複だけをmetadataで検査し、外部Runtime Adapterをimport・生成しません。
`app.open(resource_or_plan, "example-runtime", runtime=my_runtime)`で指定したAdapterだけを
load・生成し、同じアプリケーション内でキャッシュします。外部Providerと同じexport検証と
エラー分類を使います。factory結果にはDefinitionと一致する `name`、整数の `priority`、
callableな `supports` / `open` が必要です。

AdapterのインストールはRuntime実体のインストール・import・生成を意味しません。
利用者は既存の契約どおりRuntimeオブジェクトを `runtime=` で渡します。`dependencies=`へ
Runtime Adapter名を登録することはできません。公開open APIはlibrary名の明示を要求し、
指定したAdapterが非対応でも他のAdapterへfallbackしません。
組み込み・外部Runtimeのfactoryは選択時に評価します。
明示Definitionのfactoryは従来どおりconfigure時に評価します。

選択後は通常の実行経路へ渡すため、任意の `authorize()` 能力、宛先認可、credentialの
Port、独立したJSON Plan実行を維持します。未使用Adapterの `supports()` も呼び出しません。

```text
Provider / Reference
      ↓
ProviderAdapter
      ↓
Resource (Reference + AccessPlan)
                         ↓
                  RuntimeAdapter → user runtime
```

## 最小構成

`adapter_type` は実装の種類、`Provider.id` は Catalog 内での接続先の名前です。同じ
Provider Adapter を複数の Provider に再利用できます。

```python
from rhinestone import Catalog, Reference, Provider, configure
from rhinestone.adapters.contracts import (
    RuntimeAdapterDefinition,
    ProviderAdapterDefinition,
)
from rhinestone.models import AccessPlan, Metadata, Provenance, Resource


class ExampleProvider:
    def __init__(self, provider, context):
        self.provider = provider
        self.context = context

    def load(self, reference):
        uri = "https://data.example/items/example.geojson"
        return Resource(
            reference=reference,
            uri=uri,
            format="geojson",
            media_type="application/geo+json",
            metadata=Metadata(title=reference.parameters["title"]),
            provenance=Provenance(provider=self.provider.id),
            access_plan=AccessPlan(
                kind="file",
                uri=uri,
                format="geojson",
                provider=self.provider.id,
                media_type="application/geo+json",
            ),
        )


catalog = Catalog((Provider("example", "example-source"),))
app = configure(
    catalog=catalog,
    adapters=(
        ProviderAdapterDefinition(
            "example-source",
            lambda provider, context: ExampleProvider(provider, context),
        ),
    ),
)

resource = app.load(Reference("example", parameters={"title": "Example"}))
```

Provider Adapter は `load(reference) -> Resource` を必ず実装します。選択と配信形式の
解釈はAdapterの責務です。複数候補が残る場合は`AmbiguousResourceError`、0件なら
`ResourceNotFoundError`を返します。URLや形式を推測しません。

## ProviderAdapterContext（提供元アダプターへ渡す情報）

Provider factory には `ProviderAdapterContext` が渡されます。

| 属性 | 用途 |
| --- | --- |
| `transport` | 組み込み HTTP transport。`get_json()` / `get_text()` と宛先認可を一つの Port として提供 |
| `credentials` | 論理名から Credential を取得する読み取り専用 Port |
| `dependencies` | Definition が宣言した Provider依存ライブラリ を取得する読み取り専用 Port |
| `knowledge` | Identity / Time などを解決する読み取り専用 Knowledge Port |
| `destination_policy` | 通信先を認可する Policy |
| `provider_id` | 現在構成している `Provider.id` |

Provider Definition の `dependencies` に Runtime 名を宣言すると、その名前の依存が
Context に渡されます。

```python
from rhinestone.catalogs import Catalog
from rhinestone.adapters.contracts import ProviderAdapterDefinition
from rhinestone.models import RuntimeFactory

definition = ProviderAdapterDefinition(
    "rdf-source",
    make_rdf_adapter,
    dependencies=frozenset({"rdflib"}),
)

app = configure(
    catalog=Catalog((Provider("catalog", "rdf-source"),)),
    adapters=(definition,),
    dependencies={"rdflib": RuntimeFactory(load_rdflib)},
)
```

Runtime Factory は `configure()` 時には評価されず、Adapter が
`context.dependencies.get("rdflib")` を呼んだ時に初めて評価されます。Runtime 実体と
Credential secret は `Provider`、`Reference`、`AccessPlan`、`Resource` に保存しません。

外部 Adapter の安定した拡張境界は `rhinestone.adapters.contracts` の Definition と
Context、および `rhinestone.adapters.ports` の Port です。内部 Registry の storage、
process-globalな登録には依存しないでください。Providerの自動発見は上記の標準Entry Pointsを使い、
任意のthird-party Pythonは利用者のtrust boundary内で、Catalogの選択時に合成します。

地域・識別子・時間の解決は `context.knowledge` の `KnowledgePort` 契約を使います。
PLATEAU、GSI Fundamental、e-Stat GIS もこの契約を消費し、Registry の具体型や内部状態を
要求しません。各 Adapter の `knowledge=` に独自の Port 実装を直接渡すこともできます。
省略時だけ既定の Registry を使い、渡された Port の真偽値で置換しません。

認証付きHTTPでは、Credential factoryを評価する前にDestinationPolicyで宛先を認可し、
`context.credentials.get(name)`でsecretを取得します。必要な認証headerはリクエスト時だけ
組み立て、Adapterの設定やResourceに保存しないでください。
`context.transport`の`credential=`は宛先認可用の論理名であり、secretを自動取得・注入しません。
transportは送信時にも宛先を認可し、通信エラーを分類します。

次はBearer認証の提供元向けの例です。factoryが受け取った`provider`と`context`を渡します。
Providerの`endpoint`には信頼済みの実行宛先、`credential`には`custom-api-key`を構成し、
同じ論理名のCredential factoryを`configure(credentials=...)`に登録してください。
認証headerの方式はProviderの公式仕様に合わせます。

```python
def authenticated_document(provider, context, url):
    name = "custom-api-key"
    context.destination_policy.authorize(
        url,
        credentialed=True,
        provider=context.provider_id,
        service=provider.adapter_type,
        credential=name,
    )
    secret = context.credentials.get(name)
    return context.transport.get_text(
        url,
        {"Accept": "text/turtle", "Authorization": "Bearer " + secret},
        credential=name,
    )
```

Resource の URI や Provider endpoint に userinfo（`https://user:password@...`）を埋め込んでは
いけません。Rhinestone はこの形式を検証時に拒否します。File の `archive` は `zip` のみを
扱い、`entry_point` を指定する場合は安全な相対 archive path として
`AccessPlan.options` に保持してください。

## Search を追加する

複数 Provider の `search()` は最大4件まで別スレッドで並行実行されます。
Adapter の検索状態は呼び出しごとに保持し、共有する transport、Credential factory、
Runtime factory は複数スレッドから安全に呼び出せるものを渡してください。

`search(query)` は任意の機能です。実装する場合は、Adapter に対応条件を宣言します。

```python
from rhinestone.models import SearchQuery


class SearchableExampleProvider(ExampleProvider):
    search_conditions = frozenset({"text", "limit"})
    required_search_conditions = frozenset()

    def search(self, query: SearchQuery):
        # provider の公式検索 API を呼び、Resource の tuple を返す。
        # Item 単位の診断がある場合は ProviderSearchResults を返す。
        ...
```

`SearchableProviderAdapter.search()` の戻り値は `tuple[Resource, ...] | ProviderSearchResults` です。
`ProviderSearchResults(results=(...), diagnostics=(...))` により、取得できたResourceと
Item単位の診断を同じ呼び出しで返せます。例えば対象Itemに選択可能な配布物がない場合は、
`SearchDiagnostic(source_id="adapter-type", skipped_conditions=frozenset(),
reason="item_skipped", resource_identifier="item-id", detail="missing_data_asset")`
を渡します。`source_id`は設定済みProvider IDへ置き換えられます。Adapterインスタンスの
可変な状態を使って診断を受け渡しません。

宣言していない条件（例えば `bbox`）はSearch Coordinatorが除外し、
`SearchResults.diagnostics`に記録します。対応条件が一つもない場合や必須条件が不足する
場合だけ、そのProviderをskipします。Provider 横断の
ranking は行わないため、Adapter は provider 固有の結果順を保ちます。

検索結果の `Resource.reference` には配信単位を再指定できる `Reference` を保持し、`metadata` と `provenance` を
失わないようにします。検索を実装しない Adapter は `load()` だけで利用できます。

形式検索に対応するには、対象データの宣言済み形式を`Resource.formats`へ保持します。
`search_conditions`に`format`を宣言しなければ、Coordinatorが結果を絞り込み、
その後に`limit`を適用します。`format`を宣言する場合は、AdapterがOR照合、Preset展開、
`Format.UNKNOWN`の明示指定、照合後の`limit`を扱います。
URIや隣接する別データの形式から対象の形式を推測しません。

## Runtime Adapter（実行アダプター）

Runtime Adapter は Resource を選択せず、すでに選択済みの AccessPlan を Runtime
へ翻訳します。`supports` / `open` / 任意の `authorize` は `AccessPlan` を受け取ります。
Provider・Resource・provenanceへ戻って実行情報を探しません。

次の例は「最小構成」の`catalog`、`ExampleProvider`、`resource`とimportを使います。
`example_runtime`には`read(uri)`を提供する利用者所有のRuntime実体を用意してください。
新しいアプリケーションを構成するため、Catalogにある`example-source`のDefinitionも
Runtime Adapterと一緒に登録します。前のアプリケーションの登録は引き継がれません。

```python
class ExampleRuntime:
    name = "example-runtime"
    priority = 100

    def supports(self, plan):
        return plan.format == "geojson"

    def open(self, plan, runtime, *, destination_policy=None):
        return runtime.read(plan.uri)


app = configure(
    catalog=catalog,
    adapters=(
        ProviderAdapterDefinition(
            "example-source",
            lambda provider, context: ExampleProvider(provider, context),
        ),
        RuntimeAdapterDefinition(
            "example-runtime",
            lambda context: ExampleRuntime(),
        ),
    ),
)

data = app.open(resource, "example-runtime", runtime=example_runtime)
```

`supports()` は渡された AccessPlan の形式・アクセス情報だけを見て、実際の Resource
選択を行いません。公開APIでは`app.open(..., name, runtime=...)`でAdapter名とRuntimeを
明示します。指定した名前が未登録・非互換なら`RuntimeAdapterUnavailableError`となり、
別のAdapterへ切り替えません。内部Selectorの優先度規則は、公開APIのRuntime自動選択を
意味しません。Definition の `name` と生成された Adapter の `name` は一致させます。

`open()` がネットワークへアクセスする場合は、通信の前に
`destination_policy.authorize(plan.uri)` を適用するか、必要に応じて既存の
Runtime Adapter 基底クラスの `authorize()` を利用してください。Core に GDAL、Rasterio、
pyogrio などを依存させず、Runtime は `open()` で注入します。

## 登録時の制約とエラー

- 同じ Provider `adapter_type` を組み込み・custom 間で重複登録できません。
- 同じ custom Provider `adapter_type` を複数登録できません。
- Runtime の組み込み名、または custom 名の重複登録はできません。
- 未登録の `adapter_type` は暗黙に別 Adapter や URL へフォールバックしません。
- Definition の不備は `AdapterRegistrationError` または `ValueError` として早期に検出されます。
- Provider の設定不備は `ConfigValidationError`、外部 metadata の取得失敗は
  `ProviderMetadataError`、応答形式の不備は `ProviderResponseError` に分けます。

Provider Adapter は同じ入力から決定的な `Resource` を生成し、Metadata、raw metadata、Provenance を
保持してください。代表的な provider response fixture、成功ケース、曖昧な候補、未対応
条件、認証・通信失敗を Adapter package のテストに含めることを推奨します。
