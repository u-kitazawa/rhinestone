# API リファレンス

このページは Rhinestone 0.1.0 の公開 Python API を示します。利用前に
[対応状況](compatibility.md)も確認してください。表にない provider や形式は
対応しているものとして扱えません。

[Documentation home](index.md) · [Getting started](getting-started.md) ·
[Examples](../examples/README.md)

## アプリケーションを構成する

```python
from rhinestone import configure

app = configure(
    dependencies={"rasterio": lambda: rasterio},
    source_adapters=(...),
    execution_adapters=(...),
    credentials={"odpt": lambda: "consumer-key"},
)
```

### `configure(...) -> Rhinestone`

独立したアプリケーションコンテキストを作成します。グローバル状態は変更せず、
外部依存もこの時点では読み込みません。

| 引数 | 型 | 説明 |
| --- | --- | --- |
| `dependencies` | `Mapping[str, Callable[[], Any]]` | Execution Adapter 名と、対応 runtime を返す factory の対応。|
| `source_adapters` | `Iterable[ProviderAdapter]` | 使用する Source Adapter。|
| `execution_adapters` | `Iterable[ExecutionAdapter]` | 使用する Execution Adapter。|
| `credentials` | `Mapping[str, Callable[[], str]] \| None` | logical credential 名と secret factory の対応。ODPT など、対応する Adapter だけが利用する。|

factory は遅延評価されます。たとえば `lambda: rasterio` は Resource を解決する
だけでは実行されず、データを開くときに初めて評価されます。secret を `Config`
や metadata に入れないでください。

### `Rhinestone`

`configure()` が返すコンテキストです。

| メソッド | 戻り値 | 説明 |
| --- | --- | --- |
| `resolve(config: Config)` | `Resource` | Config を解決する。データは開かない。|
| `open(config: Config, adapter: str \| None = None)` | `Any` | 解決してから選択した Execution Adapter で開く。|
| `search(query: SearchQuery)` | `Mapping[str, tuple[SearchResult, ...]]` | 検索可能な Adapter を source type ごとに実行する。|

`adapter` を省略すると、登録済みで互換性のある Adapter のうち priority が最大の
ものが選ばれます。同じ priority では name が決定的なタイブレークに使われます。

## モデル

すべてのモデルは frozen dataclass です。モデルに渡した `dict`、`list`、`set` は
再帰的に読み取り専用の値へ変換されるため、解決後に変更できません。

### 入力と検索

| 型 | フィールド / メソッド | 説明 |
| --- | --- | --- |
| `Config` | `source_type: str`, `settings: Mapping[str, Any]` | Source Adapter への宣言的入力。|
| `SearchQuery` | `text`, `bbox`, `time`, `limit` | 横断検索の条件。`bbox` は `(west, south, east, north)`、`time` は `(start, end)`。各値は省略可能。|
| `SearchQuery` | `supplied_conditions` | 指定済みの条件名を返す読み取り専用集合。|
| `SearchResult` | `title`, `description`, `source_type`, `provider_settings`, `metadata`, `provenance` | 検索結果。|
| `SearchResult` | `to_config() -> Config` | 検索結果を通常の解決フローへ渡す Config に変換する。|

### 解決結果

| 型 | 主なフィールド | 説明 |
| --- | --- | --- |
| `Metadata` | `title`, `description`, `publisher`, `license`, `updated_at`, `raw` | 正規化済みと生の metadata。|
| `Provenance` | `provider`, `dataset_identifier`, `resource_identifier`, `api_endpoint`, `original_url`, `query_parameters`, `retrieved_at`, `checksum`, `adapter`, `adapter_version`, `raw` | 解決に使った出所情報。|
| `ResourceCandidate` | `uri`, `format`, `media_type`, `attributes` | Source が発見した候補。|
| `Source` | `metadata`, `candidates`, `capabilities`, `provenance`, `raw_metadata` | Source Adapter が解釈した配信元の知識。|
| `AccessPlan` | `kind`, `uri`, `options` | Resource へのアクセス方法。|
| `FileAccessPlan` | `archive` | ファイルアクセス用の AccessPlan。`kind` は `file`。|
| `RemoteDatasetPlan` | — | リモート dataset 用。`kind` は `remote-dataset`。|
| `ServiceQueryPlan` | — | サービス query 用。`kind` は `service-query`。|
| `Resource` | `uri`, `format`, `media_type`, `metadata`, `provenance`, `access_plan`, `source`, `local_path` | 選択済みの Resource。|

`Resource.open(adapter: str | None = None)` は、その Resource を解決した
`Rhinestone` コンテキストでデータを開きます。コンテキストに結び付いていない
Resource では `ExecutionAdapterUnavailableError` になります。

## 組み込み Source Adapter

各 Adapter は `rhinestone.adapters` から import します。通信を行う Adapter は、
コンストラクタの `get_json` callback に公式 API を呼ぶ関数を渡します。

| クラス | `source_type` | `Config.settings` の必須項目 |
| --- | --- | --- |
| `DirectAdapter` | `direct` | `uri`, `format` |
| `CkanAdapter` | `ckan` | `resource_id` |
| `DcatAdapter` | `dcat` | `uri`, `dataset` |
| `EStatAdapter` | `estat` | `stats_data_id` |
| `GsiFundamentalAdapter` | `gsi-fundamental` | `dataset="basic"`, `path`, `metadata` |
| `GsiTileAdapter` | `gsi-tile` | `id`、または完全な XYZ tile 定義 |
| `OdptAdapter` | `odpt` | `dataset`, `credential` |
| `OgcFeaturesAdapter` | `ogc-features` | `collection_id` |
| `PlateauAdapter` | `plateau` | `dataset_id` または `resource_id` |
| `StacAdapter` | `stac` | `collection_id`, `item_id`, `asset_key` |

任意項目や provider ごとの制約は、各 Adapter の schema で検証されます。代表例は
`endpoint`（CKAN、e-Stat、OGC API Features、PLATEAU、STAC）、`archive` と
`entry_point`（GSI Fundamental、PLATEAU）、`filters`（ODPT）です。設定の具体例は
[サンプル集](../examples/README.md)を参照してください。

`ProviderAdapter` は独自 Source Adapter の基底クラスです。`source_type` を定義し、
`load(config: Config) -> Source` を実装します。検索をサポートする場合だけ
`search(query: SearchQuery)` と `search_conditions` を実装します。

## 組み込み Execution Adapter

Execution Adapter は `rhinestone.adapters.execution` から import します。

| クラス | 選択名 / dependency 名 | 用途 |
| --- | --- | --- |
| `GdalAdapter` | `gdal` | GDAL の `OpenEx` へ変換する。|
| `RasterioAdapter` | `rasterio` | Rasterio の `open` へ変換する。|
| `PyogrioAdapter` | `pyogrio` | pyogrio の `read_dataframe` へ変換する。|
| `JsonServiceAdapter` | `json-service` | ODPT の JSON service request を実行する。|

独自 Execution Adapter は `ExecutionAdapter` を継承し、安定した `name` と `priority`、
`supports(resource, dependencies)`、`open(resource, runtime)` を実装します。Adapter
は Resource を選択せず、すでに選択された Resource を runtime の呼び出しへ変換
するだけです。

## エラー

すべて `RhinestoneError` を継承します。呼び出し側は必要な原因だけを捕捉できます。

| エラー | 発生原因 |
| --- | --- |
| `ConfigValidationError` | Config または Adapter の設定が不正。|
| `UnsupportedSourceError` | `source_type` に対応する Adapter が未登録。|
| `UnsupportedSearchConditionError` | いずれかの検索 Adapter が指定条件を扱えない。|
| `ProviderMetadataError` | provider metadata の取得に失敗。|
| `ProviderResponseError` | provider response が契約に合わない。|
| `AmbiguousResourceError` | Resource を一意に選択できない。|
| `ResourceNotFoundError` | 明示した Resource が候補にない。|
| `UnsupportedAccessError` | 既知のアクセス方法がない。|
| `ExecutionAdapterUnavailableError` | 指定または互換の Execution Adapter がない。|
| `DependencyUnavailableError` | 必要な runtime dependency が未登録または読み込めない。|
| `ResourceAccessError` | 選択済み Resource へのアクセスに失敗。|
| `IntegrityError` | integrity verification に失敗。|
| `AdapterRegistrationError` | Adapter 登録が不正または曖昧。|
| `CredentialUnavailableError` | logical credential が未設定。|
| `CredentialLoadError` | credential factory が失敗、または空の secret を返した。|

```python
from rhinestone.errors import ConfigValidationError, RhinestoneError

try:
    resource = app.resolve(config)
except ConfigValidationError as error:
    print(f"設定を確認してください: {error}")
except RhinestoneError as error:
    print(f"Rhinestone の処理に失敗しました: {error}")
```
