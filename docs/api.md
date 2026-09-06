# API リファレンス

このページはRhinestone 0.1.0の公開Python APIを示します。

[Documentation home](index.md) · [Getting started](getting-started.md) · [Source Adapter](api/source-adapters.md) · [Execution Adapter](api/execution-adapters.md)

## アプリケーションを構成する

```python
from rhinestone import configure, sources

app = configure(
    sources=sources.ALL,
    dependencies={
        "http-json": lambda: get_json,
        "rasterio": lambda: rasterio,
    },
    credentials={
        "estat": lambda: estat_app_id,
        "odpt": lambda: odpt_consumer_key,
    },
)
```

### `configure(...) -> Rhinestone`

| 引数 | 型 | 説明 |
| --- | --- | --- |
| `sources` | `Iterable[SourceDefinition]` | 利用するexternal Source。既定は空。`direct`は別途常時利用可能。|
| `dependencies` | `Mapping[str, Callable[[], Any]] \| None` | HTTP callbackやGIS runtimeを返すfactory。|
| `credentials` | `Mapping[str, Callable[[], str]] \| None` | logical credential名とsecret factory。|

runtimeとcredentialのfactoryは遅延評価されます。

### `rhinestone.sources`

組み込みexternal Source定義を提供します。

```python
sources.GEOSPATIAL_JP
sources.ESTAT
sources.PLATEAU
sources.GSI
sources.ODPT
sources.ALL
```

`sources.ALL`は上記built-in SourceDefinitionを並べたimmutableなtupleで、Coreによる特別扱いはありません。

### `SourceDefinition`

```python
SourceDefinition(
    id: str,
    adapter_type: str,
    settings: Mapping[str, Any] = {},
)
```

「どのデータ提供元を使うか」を表す静的定義です。endpointのようなSource固有値は`settings`に保持できます。credentialやruntime dependencyは保持しません。

組み込み定義がない提供元で既存Adapterを使う高度な用途では直接構築できます。

### `Rhinestone`

| メソッド | 戻り値 | 説明 |
| --- | --- | --- |
| `resolve(config: Config)` | `Resource` | Configを解決する。データは開かない。|
| `open(config: Config, adapter: str \| None = None)` | `Any` | 解決後にExecution Adapterで開く。|
| `search(query: SearchQuery)` | `Mapping[str, tuple[SearchResult, ...]]` | 検索可能な構成済みSourceを横断検索する。|

## モデル

すべてのモデルはfrozen dataclassです。渡した`dict`、`list`、`set`は再帰的に読み取り専用値へ変換されます。

### 入力と検索

| 型 | フィールド / メソッド | 説明 |
| --- | --- | --- |
| `SourceDefinition` | `id`, `adapter_type`, `settings` | 選択可能なデータ提供元の静的定義。|
| `Config` | `source_id`, `settings` | 選択済みSource内で利用する対象。endpointは原則含めない。|
| `SearchQuery` | `text`, `bbox`, `time`, `limit` | 横断検索条件。|
| `SearchQuery` | `supplied_conditions` | 指定済み条件名の読み取り専用集合。|
| `SearchResult` | `title`, `description`, `source_id`, `settings`, `metadata`, `provenance` | 検索結果。Source endpointは`settings`へ複製しない。|
| `SearchResult` | `to_config() -> Config` | 通常の解決フローへ戻すConfigを作る。|

### 解決結果

| 型 | 主なフィールド | 説明 |
| --- | --- | --- |
| `Metadata` | `title`, `description`, `publisher`, `license`, `updated_at`, `raw` | 正規化済みと生のmetadata。|
| `Provenance` | `provider`, `dataset_identifier`, `resource_identifier`, `api_endpoint`, `original_url`, `query_parameters`, `adapter`, `raw` | 出所情報。|
| `ResourceCandidate` | `uri`, `format`, `media_type`, `attributes` | Sourceが発見した候補。|
| `Source` | `metadata`, `candidates`, `capabilities`, `provenance`, `raw_metadata` | Source Adapterが解釈した知識。|
| `AccessPlan` | `kind`, `uri`, `options` | Resourceへのアクセス方法。|
| `FileAccessPlan` | `archive` | ファイルアクセス用。|
| `RemoteDatasetPlan` | — | リモートdataset用。|
| `ServiceQueryPlan` | — | service query用。|
| `Resource` | `uri`, `format`, `media_type`, `metadata`, `provenance`, `access_plan`, `source`, `local_path` | 選択済みResource。|

## Direct

`Config(source_id="direct", ...)`は`configure(sources=...)`に関係なく常時利用できます。`direct`は`sources.ALL`には含まれません。

## エラー

| エラー | 発生原因 |
| --- | --- |
| `ConfigValidationError` | Config、SourceDefinition、Adapter入力が不正。|
| `UnsupportedSourceError` | `source_id`に対応するSourceが未構成。|
| `UnsupportedSearchConditionError` | 構成済み検索Sourceが条件を扱えない。|
| `ProviderMetadataError` | provider metadataの取得に失敗。|
| `ProviderResponseError` | provider responseが契約に合わない。|
| `AmbiguousResourceError` | Resourceを一意に選択できない。|
| `ResourceNotFoundError` | 明示したResourceが候補にない。|
| `UnsupportedAccessError` | 既知のアクセス方法がない。|
| `ExecutionAdapterUnavailableError` | 指定または互換のExecution Adapterがない。|
| `DependencyUnavailableError` | 必要なruntime dependencyが未登録または読み込めない。|
| `ResourceAccessError` | Resourceへのアクセスに失敗。|
| `AdapterRegistrationError` | Source/Adapter構成が重複または不正。|
| `CredentialUnavailableError` | logical credentialが未設定。|
| `CredentialLoadError` | credential factoryが失敗または不正値を返した。|
