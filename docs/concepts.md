# 用語と概念

Rhinestone では、データ提供元の定義、提供元を解釈した結果、実際に開くデータを別の概念として扱います。

特に `SourceDefinition`、`Source`、`Resource` は名前が近いため、このページでは処理の流れに沿って役割を整理します。

## 全体像

アプリケーションを構成するときは、次の関係になります。

```text
Catalog
  -> rhinestone.sources
  -> SourceDefinition
  -> configure()
  -> Rhinestone application
```

データを利用するときは、次のパイプラインを通ります。

```text
Config
  -> [Source Adapter]
  -> Source
  -> [Resolver]
  -> AccessPlan
  -> Resource
  -> [Execution Adapter Selector]
  -> [Execution Adapter]
  -> user-provided dependency
  -> Data
```

検索はこの手前にあります。

```text
SearchQuery
  -> [Search Coordinator]
  -> searchable [Source Adapter]...
  -> SearchResult
  -> Config
  -> normal access pipeline
```

## 最初に区別したい用語

| 用語 | 一言でいうと |
| --- | --- |
| Catalog | Rhinestone が配布する固定知識 |
| `rhinestone.sources` | 組み込み `SourceDefinition` の公開窓口 |
| `SourceDefinition` | 利用可能にするデータ提供元の定義 |
| `Config` | その Source の中で利用したい対象の指定 |
| `Source` | Source Adapter が提供元を解釈した結果 |
| `Resource` | Resolver が一意に選んだ、実際に利用するデータ資源 |

最も重要なのは、`SourceDefinition` は**設定時の定義**、`Source` は**解釈結果**、`Resource` は**選択済みの利用対象**だという違いです。

## Catalog

Catalog は、接続先やサービス固有の固定知識を Rhinestone のリポジトリ側で管理するデータです。

組み込み Source は主に `src/rhinestone/catalogs/sources.json` で定義されます。Source の ID、公開名、Adapter 種別、API endpoint、Static Adapter が扱う静的サービス定義などを保持します。

Catalog に credential や GDAL、Rasterio などの runtime は保存しません。Catalog を読み込んだ結果が `SourceDefinition` になります。

## `rhinestone.sources`

`rhinestone.sources` は、Catalog から読み込んだ組み込み `SourceDefinition` を Python API 上の名前で公開する facade です。

```python
from rhinestone import sources

source = sources.GEOSPATIAL_JP
all_sources = sources.ALL
```

`sources.ALL` は特殊なモードではなく、組み込み external Source の `SourceDefinition` を並べた tuple です。

Catalog が「定義の保存場所」、`rhinestone.sources` が「利用者向けの公開窓口」です。

## `SourceDefinition`

`SourceDefinition` は「どの Source をアプリケーションで利用可能にするか」を表す静的な定義です。

- `id`: Source を識別する安定した ID
- `adapter_type`: Source を解釈する Source Adapter の種類
- `settings`: endpoint など Source 全体に固定された設定

同じ Adapter 種別を、異なる `id` と設定で複数利用できます。

`SourceDefinition.settings` には「提供元全体に固定された値」を置きます。個々の dataset、item、resource の選択は `Config` の責務です。

## `Config`

`Config` は「構成済み Source の中から、具体的に何を利用したいか」を表します。

```python
Config(
    source_id="geospatial-jp",
    settings={"resource_id": "resource-uuid"},
)
```

`source_id` は `configure()` で構成された `SourceDefinition.id` を参照します。`settings` には dataset ID、resource ID、collection ID、item 名など、その Source 内の対象指定を入れます。

原則として endpoint、HTTP client、GDAL option、credential は `Config` に入れません。

## Provider

provider は、Rhinestone が解釈する外部のデータ提供主体・サービスを指す一般概念です。

provider 固有の API schema、識別子、format 表現は Source Adapter の内部に閉じ込めます。provider は `SourceDefinition` と同義ではなく、同じ仕組みを複数の `SourceDefinition` として構成できます。

## Source Adapter

Source Adapter は、provider または Catalog 管理の静的定義と Rhinestone Core の境界です。

`Config` と `SourceDefinition` の設定を解釈し、必要なら公式の machine-readable interface から Metadata を取得して `Source` を生成します。

Source Adapter は provider 固有の Config、API request / response schema、resource 構造、format 表現、検索 API を理解します。一方、GDAL や Rasterio でデータ本体を開くことはしません。

利用者は通常、Source Adapter の instance を直接登録しません。`SourceDefinition.adapter_type` に応じて Rhinestone が構成します。

## `Source`

`Source` は Source Adapter が提供元を解釈した結果です。

```text
Source
├ Metadata
├ ResourceCandidate[]
├ capabilities
├ Provenance
└ raw metadata
```

`Source` は提供元の静的設定ではないため、`SourceDefinition` とは別物です。

## `ResourceCandidate`

`ResourceCandidate` は、`Source` の中で実際に利用する `Resource` になり得る候補です。

`uri`、`format`、`media_type`、provider 固有の補助属性を持ちます。1つの dataset に複数の配布形式がある場合、それぞれが候補になり得ます。

どの候補を利用するかを決めるのは Resolver です。

## Metadata

`Metadata` は title、description、publisher、license、updated time など、Rhinestone が共通に扱う最小限の記述情報です。

すべての provider metadata を巨大な共通 schema に変換するのではなく、共通化できる情報を `Metadata` に置き、それ以外は raw metadata として保持します。

## Raw metadata

raw metadata は、provider から得た元情報を過度に正規化せず保持する領域です。

Rhinestone の共通モデルだけでは表現できない provider 固有情報を残すために使います。

## Provenance

`Provenance` は「この Resource がどこから、どの経路で得られたか」を表す来歴情報です。

provider、dataset / resource identifier、API endpoint、original URL、query parameter、retrieved time、使用した Adapter などを保持します。

`Metadata` が「データの説明」なのに対し、`Provenance` は「取得・解決の経路」を説明します。

## Capability

Capability は、その Source または Adapter が提供できる機能の宣言です。

代表例は検索です。Search Coordinator は検索 Capability を持つ Source Adapter だけへ問い合わせます。

Capability は GDAL や HTTP client のような runtime dependency とは異なります。

## Resolver

Resolver は `Source` の `ResourceCandidate` から、実際に利用する候補とアクセス方法を決定する Core コンポーネントです。

原則としてデータ本体を読み込まず、既に得られた情報から決定的に選択します。候補を一意に決められない場合は推測せず、明示的に失敗します。

## `AccessPlan`

`AccessPlan` は「選択した Resource へどうアクセスするか」を、GDAL や Rasterio と独立して表現するモデルです。

代表的な種類は次のとおりです。

- `FileAccessPlan`: ファイルとしてアクセスする
- `RemoteDatasetPlan`: リモート dataset としてアクセスする
- `ServiceQueryPlan`: API やサービスへ query を送る

AccessPlan はアクセス方法の意味を表し、実際にどの runtime を使うかは Execution Adapter が決めます。

## `Resource`

`Resource` は Resolver によって解決された、実際に利用可能なデータ資源です。

```text
Resource
├ uri
├ format
├ media_type
├ Metadata
├ Provenance
├ AccessPlan
├ Source
└ optional local_path
```

`Resource` は単なる URL ではありません。どの Source から得られ、どの形式で、どのようにアクセスするかまで保持します。

## Execution Adapter Selector

Execution Adapter Selector は、解決済み `Resource` と利用可能な runtime dependency を見て、どの Execution Adapter を使うか決定します。

`resource.open(adapter="rasterio")` のように利用者が明示した場合は、その指定も考慮します。

## Execution Adapter

Execution Adapter は、選択済み `Resource` を GDAL、Rasterio、pyogrio など利用者所有の runtime が理解できる呼び出しへ翻訳します。

URI の渡し方、open option、layer / subdataset、service query の呼び出しなどを担当します。Resource の候補選択は行いません。

## Runtime dependency / dependency

runtime dependency は、Rhinestone がデータを開くために利用する、利用者所有の外部 runtime です。

HTTP callback、GDAL、Rasterio、pyogrio、rdflib、requests 互換 client などが該当します。`configure()` の `dependencies` に factory として渡します。

Rhinestone Core は runtime の所有や version 管理をしません。

## Credential

credential は API key や token などの secret です。

`SourceDefinition` や `Config` に埋め込まず、`configure()` の `credentials` に logical name と factory の対応として渡します。

公開 endpoint は Catalog / `SourceDefinition`、secret は credential、という分離です。

## `SearchQuery`

`SearchQuery` は複数 provider に共通して指定できる最小限の検索条件です。

現在の共通条件は `text`、`bbox`、`time`、`limit` です。Source Adapter は未対応の検索条件を黙って無視しません。

## Search Coordinator

Search Coordinator は federated search の調整役です。

検索 Capability を持つ Source Adapter へ `SearchQuery` を渡し、provider ごとの検索結果をまとめます。provider 固有 score を無理に1つの尺度へ正規化しません。

## `SearchResult`

`SearchResult` は検索で見つかった対象を、通常の解決パイプラインへ戻せる形で表します。

`source_id`、対象指定の `settings`、Metadata、Provenance などを持ち、`SearchResult.to_config()` で `Config` に変換できます。

## `Rhinestone` application / `configure()`

`configure()` は、利用する Source、runtime dependency、credential を組み合わせ、独立した `Rhinestone` application context を作ります。

この `app` が通常の利用入口です。

- `app.search(...)`
- `app.resolve(...)`
- `app.open(...)`

Adapter Registry や Dependency Registry は application context の内部実装であり、通常ユーザーが直接操作するものではありません。

## Direct

`direct` は、利用者がすでに URI や format を知っている Resource を Rhinestone の通常パイプラインへ載せる Core 機能です。

`direct` は external Source ではありません。そのため `sources.ALL` には含まれず、個別の `SourceDefinition` を構成しなくても利用できます。

## Static Adapter

Static Adapter は、外部 API から構造を発見する代わりに、Catalog または利用者が管理するレビュー済みの静的定義を `Source` として解釈する Source Adapter です。

国土地理院タイルのような静的に定義できるサービスは、専用 Adapter に接続先や layer 名を埋め込まず、Catalog の item として定義して Static Adapter で扱います。

`direct` と Static Adapter の違いは次のとおりです。

- `direct`: 利用者が URI を直接 `Config` に渡す Core 機能
- Static Adapter: 管理された静的サービス定義から item を選ぶ Source Adapter

## 内部用語: Registry

Rhinestone 内部には Adapter Registry、Dependency Registry、Credential Registry があります。

- Adapter Registry: 構成済み Source Adapter と Execution Adapter を管理する
- Dependency Registry: runtime dependency factory を管理する
- Credential Registry: credential factory を管理する

通常の利用では `configure()` を通して間接的に使います。

## 迷ったときの判断基準

| 値 | 置き場所 |
| --- | --- |
| 組み込みサービスの公開 endpoint | Catalog → `SourceDefinition.settings` |
| 利用者独自 Source の endpoint | `SourceDefinition.settings` |
| dataset / collection / resource / item の選択 | `Config.settings` |
| API key / token | credential |
| HTTP client / GDAL / Rasterio / SDK | dependency |
| provider から取得した説明情報 | `Metadata` / raw metadata |
| 取得元・解決経路 | `Provenance` |
| 候補から選ばれたアクセス方法 | `AccessPlan` |

次は、[アプリケーションを構成する](configuration.md)、[データを検索する](search.md)、[Resource を解決して開く](resolve-and-open.md)を参照してください。
