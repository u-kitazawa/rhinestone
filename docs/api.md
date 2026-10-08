# APIリファレンス

このページは、通常の利用で使う公開APIを説明します。初めて使う場合は先に[はじめに](getting-started.md)を読んでください。
用語は[用語と概念](concepts.md)、Adapterを追加する場合は[Source Adapter](api/source-adapters.md)と
[Execution Adapter](api/execution-adapters.md)を参照してください。履歴資料の`architecture/`は現行APIの規範ではありません。

## `search()`（標準構成で検索する）

通常利用では、アプリケーションを初期化せず組み込みCatalogを検索できます。標準構成は
最初の呼び出し時に遅延生成され、`configure()`で作成した独立コンテキストから変更されません。

```python
import rhinestone as rs

results = rs.search(
    text="河川",
    providers=[rs.ProviderId.GEOSPATIAL_JP],
    limit=10,
)
resource = results[0].resolve()
```

`text`、`area`、`bbox`、`time`、`format`、`limit`、`providers`の意味と診断は`Rhinestone.search()`と同じです。
独自Provider、Credential、Source Runtime、NetworkPolicy、Adapterが必要な場合は
`configure()`で独立したアプリケーションを作成します。

## `ProviderId`（組み込み提供元のID）

`ProviderId`は文字列enumです。IDEの補完で組み込みProviderを選べます。
`GEOSPATIAL_JP`、`PLATEAU`、`GSI`、`ODPT`、`MLIT_DPF`、`SEARCH_CKAN_JP`を提供します。
独自Providerは`Provider.id`の文字列で指定します。

`providers=[ProviderId.GEOSPATIAL_JP]`は検索前に対象を限定します。未選択Providerの
検索・通信は実行しません。`None`は構成済みProvider全体、`[]`は検索なしです。
未知または未構成のIDは`ConfigValidationError`になります。指定順や重複は結果順を変えず、
Catalog順で各Providerを1回だけ検索します。解決専用Providerは検索を行いません。

## `Catalog`（提供元の一覧）

データ提供元の設定をまとめた、変更されない一覧です。組み込みCatalogは`rhinestone.catalogs.BUILTIN`です。

```python
from rhinestone.catalogs import BUILTIN
```

## `Provider`（データ提供元）

Catalogからアプリケーションへ登録するデータ提供元です。

```python
from rhinestone import Provider

provider = Provider(
    id="my-stac",
    adapter_type="stac",
    settings={"endpoint": "https://stac.example/api"},
)
```

`adapter_type`と`settings`はProviderを構成する拡張向け情報です。secretやRuntimeは保持しません。
`Provider`は不変なので、設定を変更する場合は新しいProviderまたはCatalogを作成します。

## `Config`（解決設定）

`Config`は、構成済みProviderを選び、そのAdapterへ渡す解決条件です。
`source_id`はCatalog内のProvider IDと一致している必要があります。Provider固有の例として、
CKANなら`resource_id`、STACなら`collection_id`・`item_id`・`asset_key`を指定します。

```python
from rhinestone import Config

config = Config("my-stac", {
    "collection_id": "sentinel-2",
    "item_id": "scene-1",
    "asset_key": "visual",
})
resource = app.resolve(config)
```

## `configure()`（アプリケーションを作る）

Catalog、Source Runtime、Credentialを組み合わせて`Rhinestone`アプリケーションを作ります。
Execution Runtimeは`open()`で渡します。

```python
import os

from rhinestone import configure
from rhinestone.catalogs import BUILTIN

app = configure(
    catalog=BUILTIN,
    credentials={"odpt": lambda: os.environ["ODPT_CONSUMER_KEY"]},
    network_policy="credentialed",
)
```

| 引数 | 説明 |
| --- | --- |
| `catalog` | 利用するProviderのCatalog |
| `dependencies` | 検索・解決用のSource Runtime実体または`RuntimeFactory`。Execution Runtimeは受け付けない |
| `credentials` | 認証情報を取得するfactory |
| `network_policy` | 宛先制限。`none` または `credentialed`（既定） |
| `adapters` | `SourceAdapterDefinition`／`ExecutionAdapterDefinition`／`KnowledgeAdapterDefinition` の iterable。組み込みは自動登録され、独自定義だけを指定する |

独自構成が必要なコードでは`catalog`を使ってください。
Source Runtimeの遅延読み込みには`RuntimeFactory(factory)`を指定します。Execution Runtimeは`open(..., runtime=...)`で実体を渡します。

Provider の `settings` に `credential` を論理名として指定すると、CKAN、STAC、OGC
などの HTTP Source へ Credential factory を遅延注入できます。secret 自体は
Provider、Catalog、Result、Resource には保存されません。`credentialed` では、factory の
評価前に Catalog 由来の endpoint へ送信できることを検証します。

## `Rhinestone.search()`（データを検索する）

Catalogに構成されたProvider内のデータ候補を検索し、Resultを返します。Provider自体を発見するAPIではありません。

```python
results = app.search(text="河川", limit=10)
result = results[0]
```

`text`、`area`、`bbox`、`time`、`format`、`limit`、`providers`をキーワードで指定できます。`area`は行政区域名・別名・コードを受け取り、bbox対応SourceにはCRS84 bbox、明示的なtext fallbackを持つSourceには正式区域名として投影されます。`area`と`bbox`は同時指定できず、未知区域はProvider呼び出し前に`area_resolution_failed` diagnosticになります。`SearchQuery`を直接渡す場合は
`rhinestone.models`からimportします。

`format`は`Format`または`FormatPreset`の空でないtupleで指定し、複数値はOR条件です。
文字列やlistは`ConfigValidationError`になります。`limit`はProviderごとの上限であり、
横断検索全体の上限ではありません。既定の`None`は全件取得を保証しません。
具体的な適用段階とpage制限は[検索能力の対照表](search-capabilities.md)を参照してください。

位置引数`query`には`SearchQuery`または検索文字列を渡せます。`query`とキーワード検索条件の
併用は`TypeError`になります。この呼び出し契約はトップレベルの`search()`と共通です。

`SearchResults`のiterationと整数indexingは、構成したProvider順にgroupを連結し、
各Provider内の順序を保持します。このsequenceは決定的な走査用であり、Providerを
横断した関連度rankingではありません。Provider固有のrankingを扱う場合は
`results.items()`または`results["provider-id"]`でgroupごとに参照します。

## `Result`（検索結果）

検索で見つかった候補です。通常は次のようにResourceへ解決します。

```python
resource = result.resolve()
```

`title`、`description`、`discovered_by`、`target`、`metadata`、`raw_metadata`、`provenance`、
`formats`を参照できます。`target`は解決先の`Config`で、`to_config()`でも取得できます。
`formats`は検索時に宣言された形式の`frozenset[str]`です。`Resource.format`の保証ではありません。
Coordinatorによる形式照合では、空の場合や`Format`の値へ正規化できない場合に不明として
扱います。一方、CKAN、PLATEAU、search.ckan.jpのAdapter内照合では、非空の未登録形式
（例：`xlsx`）は`Format.UNKNOWN`に一致しません。こうした形式を取得する場合は`format`を
省略して検索し、`result.formats`を確認してください。詳しくは
[検索能力の対照表](search-capabilities.md)を参照してください。

検索結果の一部条件がSourceで適用されなかった場合や、必須条件不足でSourceがskipされた場合は、`SearchResults.diagnostics`でSourceごとの診断を確認できます。`reason`と`missing_conditions`も参照できます。Providerの通信・metadata・response障害は`reason="provider_failure"`、`failure_type`（`metadata`または`response`）として診断され、他のSourceの結果は継続して返されます。必要なCredentialが未登録の場合は`failure_type="credential"`です。Credential factoryの失敗や予期しないプログラムエラーはこの診断へ変換されません。

`Result.metadata`、`Result.raw_metadata`、`Result.provenance`は検索時の情報です。`app.resolve(result)`は
cross-source解決後もこれらを`resource.discovery`へ保持し、target Sourceが生成した
`resource.metadata`、`resource.provenance`、`resource.source.raw_metadata`を上書きしません。
アプリケーションから独立して作成したResultでは
`result.resolve()`を使えないため、`app.resolve(result)`を使用してください。

## `SearchResults`（提供元別の検索結果）

整数index・iterationはProvider順の結果列、sliceは`tuple[Result, ...]`、文字列indexは
該当Providerの結果tupleを返します。`keys()`、`values()`、`items()`、`get()`で
Provider別に参照できます。条件の診断は`diagnostics`、実行したProviderの
`source_id`・`elapsed_ms`・`result_count`は`executions`で確認できます。
結果が空でも、Provider障害などの理由を診断から調べられます。

## `Rhinestone.resolve()`（Resourceを確定する）

`Result`または高度な`Config`をResourceへ解決します。

```python
resource = app.resolve(result)
```

## `Resource`（利用するデータ）

解決済みの具体的なデータです。`uri`、`format`、`media_type`、`metadata`、`provenance`を持ち、Runtimeを明示して開きます。cross-source解決では、発見側の`metadata`、`raw_metadata`、`provenance`が`discovery`に入り、target側の記録と分離されます。

```python
data = resource.open("rasterio", runtime=rasterio)
```

ResourceはResolverが候補を一意に選び、明示的な`AccessPlan`を作成した後の値です。

### Portable Result / Resource

`Result.to_dict()` / `Resource.to_dict()`はversion付きのJSON-safeな値を返します。
現在の`rhinestone.result`はversion 1、単一AccessPlan契約を含む
`rhinestone.resource`はversion 2です。credential、runtime、resolver、openerは
含みません。`Result.from_dict()` / `Resource.from_dict()`で復元した値はdetachedなので、
別のApplicationで`app.bind(value)`してから`result.resolve()`または
`resource.open(...)`を利用します。未知のschema/versionやJSON-safeでないraw metadataは
`ConfigValidationError`として拒否されます。

`access_plan.kind`は`file`、`remote-dataset`、`service-query`のいずれかです。
`AccessPlan`は派生型を持たない単一の値型で、`uri`、`format`、`media_type`、
`options`、`provider`、`service`、論理credential参照を保持します。
`to_dict()` / `from_dict()` は `rhinestone.access-plan` schema のversion付きJSON契約を
生成・検証します。secretやruntime objectは含められません。受信側は実行前に
`DestinationPolicy.authorize_plan()`でURI、tile URL、redirect先を再検証できます。
`Resource.open()`はデータ解析を行わず、指定した利用者所有Runtimeへ処理を委譲します。

`library`は必須です。外部Runtimeは`runtime=`へ実体を渡し、`RuntimeFactory`は
受け付けません。未登録・非互換のAdapterやRuntime不足は
`ExecutionAdapterUnavailableError`となり、別Runtimeへ自動で切り替えません。
`json-service`はCoreのRuntimeを使うため`resource.open("json-service")`とし、
`runtime=`を省略します。この契約は`Rhinestone.open()`にも共通です。

## `Format` / `FormatPreset`（検索形式）

```python
from rhinestone import Format, FormatPreset

results = app.search(text="河川", format=(Format.GEOJSON, Format.GPKG))
vectors = app.search(text="河川", format=(FormatPreset.PYOGRIO,), limit=10)
```

`Format`は共通の形式名を表すEnumです。形式不明には`Format.UNKNOWN`を明示します。
`FormatPreset.PYOGRIO`は`SHAPEFILE`、`GEOJSON`、`GPKG`、`FLATGEOBUF`、`GML`、
`KML`、`CITYGML`の集合へ展開されます。Presetは検索候補集合であり、解決やRuntimeの
open成功を保証しません。検索時に形式が設定されないProviderを含む制限は
[検索能力の対照表](search-capabilities.md)の「形式検索の適用段階」を参照してください。

## エラー処理

期待される失敗は`rhinestone.errors`の型で分類されます。通常は次のように、原因に応じて
利用者へ案内したり再試行したりします。

```python
from rhinestone.errors import (
    AmbiguousResourceError,
    ProviderMetadataError,
    ResourceNotFoundError,
)

try:
    resource = app.resolve(config)
except ResourceNotFoundError:
    print("selection did not match a resource; check provider identifiers")
except AmbiguousResourceError:
    print("more than one resource matched; add an explicit selector")
except ProviderMetadataError:
    print("provider metadata was unavailable; retry or inspect the endpoint")
```

主な分類は次のとおりです。

- `ConfigValidationError`: Config、検索条件、Catalog、Adapter定義の入力不正
- `UnsupportedSourceError`: 未構成のSource ID
- `ProviderMetadataError` / `ProviderResponseError`: 通信・Provider応答の失敗
- `ResourceNotFoundError` / `AmbiguousResourceError`: Resource選択の失敗
- `UnsupportedAccessError`: formatまたはAccessPlanが未対応・不明
- `ExecutionAdapterUnavailableError` / `DependencyUnavailableError`: Runtime不足または非互換
- `ResourceAccessError` / `DestinationNotAllowedError`: 実データアクセスまたは宛先制限の失敗
- `CredentialUnavailableError` / `CredentialLoadError`: 論理Credentialの設定・factory失敗

例外メッセージには、原因を調べるためのフィールド名、Source ID、Adapter名、候補数などが
含まれます。Credentialのsecret、raw payload、過長なレスポンスは含まれません。Providerの
検索障害はSource単位で`SearchResults.diagnostics`へ隔離されますが、予期しないプログラム
エラーは握りつぶされません。

## 拡張・Adapter向けAPI

通常利用のトップレベルAPIは、`search`、`configure`、`Rhinestone`、`Catalog`、`Provider`、`Config`、
`Format`、`FormatPreset`、
`Result`、`SearchResults`、`Resource`に限定しています。
Provider固有のSourceを実装したり、実行Adapter・Knowledge Adapterを追加したりする場合は、
次のサブモジュールを正式な拡張surfaceとして利用してください。

- `rhinestone.models`: `Source`、`ResourceCandidate`、`AccessPlan`系、`Metadata`、`Provenance`、
  `SearchQuery`、`SearchDiagnostic`、`RuntimeFactory`、`Dependencies`などのドメイン型
- `rhinestone.adapters.contracts`: Adapter Definition、Context、Factory、Protocol
- `rhinestone.adapters.knowledge`: Knowledge AdapterのDefinition、Context、Registry、型
- `rhinestone.security`: `DestinationPolicy`と宛先ルール
- `rhinestone.representations`: format定義と正規化関数

各サブモジュールの`__all__`が、その拡張surfaceの公開名を示します。Adapterの登録方法は
[Custom Adapterを作る](custom-adapters.md)を参照してください。

## 形式名の共通定義

Source Adapter 間で共有する format 名と media type 対応は
`rhinestone.representations` から利用できます。

```python
from rhinestone.representations import canonical_format, format_from_media_type

assert canonical_format("GeoPackage") == "gpkg"
assert format_from_media_type("image/tiff") == "geotiff"
```

format の alias と既知の media type だけを正規化し、URL の拡張子から format は推測しません。
`FORMAT_ALIASES`、`MEDIA_TYPE_FORMATS`、`FORMAT_CATEGORIES` は共有定義です。
Execution Adapter がどの format を実行できるかは、各 Adapter の capability として管理されます。

## `Rhinestone.open()`（データを開く）

Resourceを渡すか、Result/Configを渡して解決とopenを一度に行えます。

```python
data = app.open(result, "rasterio", runtime=rasterio)
```

## `Runtime`（外部ライブラリ）

GDAL、Rasterio、pyogrio、RDFLibなど、利用者が所有する外部実行環境です。RDFLibはDCATの検索・解決時に、GDAL、Rasterio、pyogrioは`Resource.open()`時に必要になります。HTTP JSON、HTTP text、JSON serviceは組み込みRuntimeを使用します。インストール例と検証済み範囲は[Runtimeの導入ガイド](runtimes.md)を参照してください。

```python
from rhinestone.models import RuntimeFactory
```

## 高度なモデル

`Source`、`ResourceCandidate`、`AccessPlan`、`SearchQuery`、`SearchDiagnostic`は、
`rhinestone.models`経由で利用する拡張・Adapter向けモデルです。`Config`、`Provider`、
`Result`、`Resource`は通常利用と拡張の両方で使う中核モデルです。
