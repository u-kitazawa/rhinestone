# Custom Adapter を作る

Rhinestone の Adapter は、Provider 固有の情報を共通の `Source` へ変換する Source
Adapter と、解決済みの `Resource` を外部 Runtime へ渡す Execution Adapter に分かれます。
どちらも `configure(adapters=...)` へ明示登録します。組み込み Adapter も
「あらかじめ登録された Definition」として同じ Registry に追加されるため、Custom Adapter
と同じ Factory／Context／選択経路を通ります。Adapter package の自動発見や process-global
な登録は行いません。

```text
Provider / Config
      ↓
SourceAdapter
      ↓
Source → Resolver → Resource
                         ↓
                  ExecutionAdapter → user runtime
```

## 最小構成

`adapter_type` は実装の種類、`Provider.id` は Catalog 内での接続先の名前です。同じ
Source Adapter を複数の Provider に再利用できます。

```python
from rhinestone import (
    Catalog,
    Config,
    ExecutionAdapterDefinition,
    Metadata,
    Provider,
    Provenance,
    ResourceCandidate,
    Source,
    SourceAdapterDefinition,
    configure,
)


class ExampleSource:
    def __init__(self, provider, context):
        self.provider = provider
        self.context = context

    def load(self, config):
        # Config.settings を検証し、provider の応答を Source に変換する。
        return Source(
            metadata=Metadata(title=config.settings["title"]),
            candidates=(ResourceCandidate(
                uri="https://data.example/items/example.geojson",
                format="geojson",
                media_type="application/geo+json",
            ),),
            capabilities=frozenset(),
            provenance=Provenance(
                provider=self.provider.id,
                adapter="example-source",
                original_url="https://data.example/items/example.geojson",
            ),
            raw_metadata={"title": config.settings["title"]},
        )


catalog = Catalog((Provider("example", "example-source"),))
app = configure(
    catalog=catalog,
    adapters=(SourceAdapterDefinition(
        "example-source",
        lambda provider, context: ExampleSource(provider, context),
    ),),
)

resource = app.resolve(Config("example", {"title": "Example"}))
```

Source Adapter は `load(config) -> Source` を必ず実装します。Source の候補が複数ある
場合の選択は Adapter ではなく Resolver の責務です。Adapter は URL や形式を推測せず、
判断できない場合は専用のエラーを送出してください。

## SourceAdapterContext

Source factory には `SourceAdapterContext` が渡されます。

| 属性 | 用途 |
| --- | --- |
| `get_json(url, params, headers=None)` | 組み込み HTTP JSON transport |
| `get_text(url)` | 組み込み HTTP text transport |
| `credentials` | 論理名から Credential を取得する Registry |
| `dependencies` | Definition が宣言した Source Runtime の Registry |
| `destination_policy` | 通信先を認可する Policy |
| `provider_id` | 現在構成している `Provider.id` |

Source Definition の `dependencies` に Runtime 名を宣言すると、その名前の依存が
Context に渡されます。

```python
from rhinestone import RuntimeFactory, SourceAdapterDefinition

definition = SourceAdapterDefinition(
    "rdf-source",
    make_rdf_adapter,
    dependencies=frozenset({"rdflib"}),
)

app = configure(
    sources=(Provider("catalog", "rdf-source"),),
    adapters=(definition,),
    dependencies={"rdflib": RuntimeFactory(load_rdflib)},
)
```

Runtime Factory は `configure()` 時には評価されず、Adapter が
`context.dependencies.get("rdflib")` を呼んだ時に初めて評価されます。Runtime 実体と
Credential secret は `Provider`、`Config`、`Source`、`Resource` に保存しません。

認証付き HTTP は secret を自前の header に埋め込まず、`context.credentials.get(name)` を
使います。`context.get_json()` と DestinationPolicy を使うことで、組み込み transport の
エラー分類と通信先制限を維持できます。

## Search を追加する

`search(query)` は任意の機能です。実装する場合は、Adapter に対応条件を宣言します。

```python
from rhinestone import SearchQuery


class SearchableExampleSource(ExampleSource):
    search_conditions = frozenset({"text", "limit"})
    required_search_conditions = frozenset()

    def search(self, query: SearchQuery):
        # provider の公式検索 API を呼び、Result の tuple を返す。
        ...
```

宣言していない条件（例えば `bbox`）を受け取った場合、Search Coordinator がその
Provider を skip し、`SearchResults.diagnostics` に理由を記録します。Provider 横断の
ranking は行わないため、Adapter は provider 固有の結果順を保ちます。

検索結果の `target` は通常の `Config` に戻せる形にし、`metadata` と `provenance` を
失わないようにします。検索を実装しない Adapter は `load()` だけで利用できます。

## Execution Adapter

Execution Adapter は Resource を選択せず、すでに Resolver が選んだ Resource を Runtime
へ翻訳します。

```python
class ExampleExecution:
    name = "example-runtime"
    priority = 100

    def supports(self, resource, dependencies):
        return (
            resource.format == "geojson"
            and self.name in dependencies
        )

    def open(self, resource, runtime, *, destination_policy=None):
        return runtime.read(resource.uri)


app = configure(
    catalog=catalog,
    adapters=(ExecutionAdapterDefinition(
        "example-runtime",
        lambda context: ExampleExecution(),
    ),),
    dependencies={"example-runtime": example_runtime},
)

data = app.open(resource, "example-runtime")
```

`supports()` は Resource の形式・AccessPlan・利用可能な依存だけを見て、実際の Resource
選択を行いません。`priority` が大きい Adapter が自動選択され、`app.open(..., name)` で
明示選択もできます。Definition の `name` と生成された Adapter の `name` は一致させます。

`open()` がネットワークへアクセスする場合は、Runtime を解決する前に
`destination_policy.authorize(resource.uri)` を適用するか、必要に応じて既存の
Execution Adapter 基底クラスの `authorize()` を利用してください。Core に GDAL、Rasterio、
pyogrio などを依存させず、Runtime は常に `dependencies` から注入します。

## 登録時の制約とエラー

- 同じ Source `adapter_type` を組み込み・custom 間で重複登録できません。
- 同じ custom Source `adapter_type` を複数登録できません。
- Execution の組み込み名、または custom 名の重複登録はできません。
- 未登録の `adapter_type` は暗黙に別 Adapter や URL へフォールバックしません。
- Definition の不備は `AdapterRegistrationError` または `ValueError` として早期に検出されます。
- Provider の設定不備は `ConfigValidationError`、外部 metadata の取得失敗は
  `ProviderMetadataError`、応答形式の不備は `ProviderResponseError` に分けます。

Adapter は同じ入力から決定的な `Source` を生成し、Metadata、raw metadata、Provenance を
保持してください。代表的な provider response fixture、成功ケース、曖昧な候補、未対応
条件、認証・通信失敗を Adapter package のテストに含めることを推奨します。
