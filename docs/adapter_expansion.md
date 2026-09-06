# Rhinestone Adapter Expansion Specification v0.1

## 1. 対象

本仕様では、以下の［Source Adapter］を追加する。

```text
1. ［GSI Tile Adapter］
2. ［PLATEAU Adapter］
3. ［GSI Fundamental Data Adapter］
4. ［DCAT Adapter］
5. ［ODPT Adapter］
```

実装優先順位もこの順とする。

---

# 2. 共通設計原則

各Adapterは、既存のRhinestone Coreモデルを変更することなく追加できることを基本とする。

共通フロー:

```text
Config
  ↓
［Source Adapter］
  ↓
Source
  ↓
［Resolver］
  ↓
AccessPlan
  ↓
Resource
```

AdapterはProvider固有の知識を持つが、CoreへProvider固有構造を漏らさない。

---

# 3. Adapter追加時の原則

新しい［Source Adapter］は以下を満たす。

1. Provider固有のAPI・ID・metadata構造を理解する。
2. Provider固有Configを受け取れる。
3. Configを検証する。
4. Providerの公式machine-readable interfaceのみを原則利用する。
5. HTML scrapingを行わない。
6. 取得したraw metadataを保持する。
7. Metadata / Provenanceを捨てない。
8. Resourceの実データ型へ無理に変換しない。
9. ［Execution Adapter］が必要とする情報をResourceへ保持する。
10. 不明な仕様を推測しない。

---

# 4. ［GSI Tile Adapter］

## 4.1 目的

国土地理院が提供する地理院タイルをRhinestoneから統一的に扱う。

地理院タイルは、国土地理院が配信するタイル状の地図データであり、標準地図、淡色地図、写真、各種主題図等が提供されている。標準地図では `https://cyberjapandata.gsi.go.jp/xyz/std/{z}/{x}/{y}.png` のようなXYZ形式のURLが公式に公開されている。citeturn612884search0turn612884search6

---

## 4.2 Adapter

GSIタイル専用のAdapterは追加しない。既存の汎用 `StaticAdapter` を使用し、
GSI固有の固定知識はCatalog itemとして管理する。

`SourceDefinition` は次のように構成する。

```yaml
source:
  id: gsi
  adapter_type: static
```

---

## 4.3 Config

Catalogの `sources.json` に定義されたitem名を `id` で指定する。

```python
from rhinestone import Config

Config("gsi", {"id": "std"})
Config("gsi", {"id": "pale"})
```

URL templateをConfigへ直接指定せず、接続先とtile仕様はCatalogに保持する。
これにより、Configは選択対象だけを表し、CoreやAdapterがGSI固有の名前を知る必要がない。

---

## 4.4 Specとして保持する知識

［StaticAdapter］は最低限以下を知る。

```text
tile id
title
URL template
tile scheme
format
media type
min zoom
max zoom
coverage
attribution
usage notes
provider
```

例:

```text
id          = std
scheme      = xyz
format      = png
media_type  = image/png
provider    = GSI
```

---

## 4.5 利用条件

地理院タイルは種類ごとに利用条件が異なる可能性があるため、Metadataに利用条件を保持する。

特に、

```text
attribution
license / usage category
usage URL
notes
```

を保持する。

国土地理院は、タイルによって基本測量成果、出典明示のみで利用できるもの、その他の条件があるものに分類している。リアルタイム利用では出典明示で利用可能なケースもあるが、個別タイルごとの条件を確認する必要がある。citeturn612884search0

Rhinestoneは法的可否を推測しない。

---

## 4.6 Source

概念例:

```text
Source
├ Metadata
│  ├ title
│  ├ provider = GSI
│  ├ attribution
│  ├ usage
│  └ raw metadata
├ Resource候補
└ Provenance
```

---

## 4.7 Resource

Resource概念例:

```text
Resource
├ uri_template
├ format = png
├ media_type = image/png
├ tile_scheme = xyz
├ min_zoom
├ max_zoom
├ Metadata
├ Provenance
└ AccessPlan
```

---

## 4.8 AccessPlan

タイルは原則としてRemote Datasetとして扱う。

```text
RemoteDatasetPlan
```

URL templateをAccessPlanに保持する。

---

## 4.9 Execution Adapter連携

将来的に以下への接続を想定する。

```text
［GdalAdapter］
［RasterioAdapter］
［MapLibreAdapter］
［QgisAdapter］
```

ただし［StaticAdapter］自身がMapLibreやGDALに依存してはならない。

---

## 4.10 Search

初期実装ではRhinestone内部の既知Specから検索してよい。

例:

```python
app.search(SearchQuery(text="標準地図"))
```

結果には、

```text
title
id
description
format
zoom range
usage metadata
Config
```

を含める。

外部検索APIを無理に作らない。

---

## 4.11 Fail Rather Than Guess

以下の場合は失敗する。

```text
unknown tile id
invalid URL template
unsupported tile scheme
missing required metadata when required for execution
```

URLからtile IDを推測しない。

---

# 5. ［PLATEAU Adapter］

## 5.1 目的

国土交通省Project PLATEAUの3D都市モデルを統一的に取得・解釈する。

PLATEAUのオープンデータはG空間情報センターから公開されており、2026年5月時点で306地域が掲載されている。citeturn612884search3

---

## 5.2 Adapter

```text
［PlateauAdapter］
```

を追加する。

Config:

```yaml
source:
  type: plateau
```

---

## 5.3 Config

代表的なConfig:

```yaml
source:
  type: plateau
  city: "13100"
  year: 2025
  format: citygml
```

必要に応じて、

```yaml
source:
  type: plateau
  city: "13100"
  year: 2025
  feature_type: bldg
```

等を許可する。

---

## 5.4 Specとして保持する知識

［PlateauAdapter］は最低限以下を扱う。

```text
municipality
municipality code
dataset year
revision/version
feature type
LOD
distribution format
download resource
license
source catalog metadata
```

対象format候補:

```text
CityGML
3D Tiles
GeoPackage
その他公式distribution
```

実際に存在するdistributionのみResource候補とする。

---

## 5.5 Provider構造

PLATEAUそのものと、実際の配布基盤を区別する。

```text
PLATEAU
  ↓
official metadata / catalog
  ↓
G Spatial Information Center distribution
```

Rhinestoneでは、

```text
provider = PLATEAU
distribution_provider = actual catalog/distribution provider
```

のようにProvenanceを失わない。

---

## 5.6 Source

```text
Source
├ Metadata
│  ├ city
│  ├ municipality_code
│  ├ year
│  ├ version
│  ├ license
│  └ raw metadata
├ Resource候補[]
└ Provenance
```

---

## 5.7 Resource選択

Configでformatやfeature typeが明示されている場合、その条件に一致するResourceのみを選択する。

複数候補があり、優先順位が仕様化されていない場合、

```text
AmbiguousResourceError
```

とする。

勝手にCityGMLや3D Tilesを優先してはならない。

---

## 5.8 AccessPlan

配布形態に応じて、

```text
FileAccessPlan
RemoteDatasetPlan
```

を選択する。

---

## 5.9 Execution Adapter連携

想定:

```text
CityGML
→ ［GdalAdapter］等

GeoPackage
→ ［GdalAdapter］
→ ［PyogrioAdapter］

3D Tiles
→ 将来の対応Adapter
```

PLATEAU固有の変換処理を［PlateauAdapter］へ埋め込まない。

---

## 5.10 Search

検索条件候補:

```text
city
municipality_code
year
feature_type
format
text
```

検索結果は必ずConfigへ変換可能であること。

---

## 5.11 Example

```python
results = rs.search(
    "新宿区 建築物",
    adapters=["plateau"],
)

resource = rs.fetch(results[0].config)
```

---

# 6. ［GSI Fundamental Data Adapter］

## 6.1 目的

国土地理院の基盤地図情報をRhinestoneから扱う。

対象:

```text
基盤地図情報 基本項目
数値標高モデル
```

---

## 6.2 Adapter

```text
［GsiFundamentalAdapter］
```

Config:

```yaml
source:
  type: gsi-fundamental
```

---

## 6.3 認証

基盤地図情報ダウンロードサービスでは利用者登録とログインが必要である。citeturn612884search4

認証情報をConfigへ直接格納しない。

例:

```yaml
source:
  type: gsi-fundamental
  dataset: dem
  credential: gsi
```

Credential実体は外部注入とする。

```text
［Credential Registry］
```

を将来的に利用可能とする。

---

## 6.4 Config

例:

```yaml
source:
  type: gsi-fundamental
  dataset: dem
  mesh: "533945"
  resolution: 5m
```

基本項目:

```yaml
source:
  type: gsi-fundamental
  dataset: basic
  mesh: "533945"
```

---

## 6.5 Specとして保持する知識

重要なSpec:

```text
dataset type
mesh system
resolution
DEM type
schema version
download specification version
CRS
format
archive structure
filename convention
release date
```

---

## 6.6 Schema Version

基盤地図情報では歴代XML Schemaが存在する。

2025年4月以降はXML Schema 5.1が提供されており、2026年7月31日以降のデータについてはダウンロードデータ仕様5.3が公開されている。citeturn612884search1turn612884search5

RhinestoneはSchema versionをResource Metadataとして保持する。

```text
schema_version
download_spec_version
```

---

## 6.7 CRS

最新提供データではJGD2011からJGD2024への移行が行われている。citeturn612884search4turn612884search5

したがって、

```text
crs
datum
specification_date
```

を明示的にResourceへ保持する。

ファイル名や日付だけから不確実にCRSを推測してはならない。

公式metadataまたはSchemaに基づいて判定する。

---

## 6.8 DEM

DEMについて以下をSpec化する。

例:

```text
DEM1A
DEM5A
DEM5B
DEM5C
DEM10A
DEM10B
```

国土地理院はこれらの種別と作成元、ファイル命名規則を公開している。citeturn612884search2

Metadataには、

```text
resolution
dem_type
production_method
mesh
```

を保持する。

---

## 6.9 Resource

例:

```text
Resource
├ format = GML/XML
├ archive = zip
├ schema_version = 5.1
├ crs = JGD2024
├ mesh
├ dem_type
├ Metadata
├ Provenance
└ AccessPlan
```

---

## 6.10 Execution Adapter連携

想定:

```text
［GdalAdapter］
```

等。

GML/XMLの解析方法は［Execution Adapter］側へ委譲する。

［GsiFundamentalAdapter］はSchemaやResource構造を知るが、GISオブジェクトへ変換しない。

---

# 7. ［DCAT Adapter］

## 7.1 目的

DCAT互換データカタログをRhinestoneの共通Sourceとして扱う。

DCAT 3は2024年8月22日にW3C Recommendationとなっており、Dataset、Distribution、DataService、DatasetSeries等を標準モデルとして定義している。citeturn862912search0turn862912search2

---

## 7.2 Adapter

```text
［DcatAdapter］
```

Config:

```yaml
source:
  type: dcat
```

---

## 7.3 Config

Dataset URI指定:

```yaml
source:
  type: dcat
  catalog: https://example.org/catalog
  dataset: https://example.org/dataset/123
```

直接RDF指定:

```yaml
source:
  type: dcat
  uri: https://example.org/catalog.jsonld
```

---

## 7.4 対応serialization

最低限候補:

```text
JSON-LD
Turtle
RDF/XML
```

DCAT自体は特定serializationを要求せず、RDFとして複数表現を利用できる。citeturn862912search2

RDF parserの実装を独自に持つ必要はない。

既存RDFライブラリを利用する。

---

## 7.5 DCATとRhinestoneの対応

基本mapping:

```text
dcat:Dataset
→ Source

dcat:Distribution
→ Resource候補

dcat:DataService
→ Service AccessPlan候補

dcat:Catalog
→ Search対象

dcat:CatalogRecord
→ Provenance / Metadata

dcat:DatasetSeries
→ Source relation
```

DCATではDatasetとDistributionが明確に分離されており、DistributionはCSV等の実際にアクセス可能な形態を表す。これはRhinestoneのSource / Resource分離と非常に相性が良い。citeturn862912search2

---

## 7.6 Distribution

以下を優先的に読む。

```text
downloadURL
accessURL
mediaType
format
byteSize
title
license
```

ただし、複数Distributionから勝手に1つを選択しない。

---

## 7.7 DataService

DataServiceが存在する場合、

```text
ServiceQueryPlan
```

または適切なAccessPlan候補へ変換する。

サービスの詳細仕様が不明な場合は、EndpointだけをResource Metadataとして保持し、無理にExecution可能Resourceへ変換しない。

---

## 7.8 Search

DCATは分散型catalog/federated searchとの親和性を前提とするため、Rhinestoneの［Search Coordinator］と組み合わせる。citeturn862912search0turn862912search2

SearchResult:

```text
SearchResult
├ title
├ description
├ dataset URI
├ Metadata
├ distributions
└ Config
```

---

## 7.9 Profile

DCAT Profile固有拡張をCoreへ持ち込まない。

```text
DCAT-AP
国内DCAT profile
organization-specific vocabulary
```

等はraw metadataとして保持し、必要になればAdapter内部のprofile処理として追加する。

---

# 8. ［ODPT Adapter］

## 8.1 目的

公共交通オープンデータセンターが提供する公共交通データをRhinestoneから扱う。

ODPTのAPI利用にはユーザー登録とAPIキーが必要である。citeturn862912search3

---

## 8.2 Adapter

```text
［OdptAdapter］
```

Config:

```yaml
source:
  type: odpt
```

---

## 8.3 Credential

ConfigにAPI tokenを直接入れない。

例:

```yaml
source:
  type: odpt
  dataset: railway
  credential: odpt
```

runtime:

```python
rs = Rhinestone(
    credentials={
        "odpt": lambda: os.environ["ODPT_API_KEY"],
    }
)
```

認証方法を理解するのは［OdptAdapter］であり、tokenの実体を所有するのはユーザーである。

---

## 8.4 Config

概念例:

```yaml
source:
  type: odpt
  dataset: railway
  operator: odpt.Operator:JR-East
```

列車情報:

```yaml
source:
  type: odpt
  dataset: train
  operator: ...
```

駅情報:

```yaml
source:
  type: odpt
  dataset: station
```

正確なdataset名、parameter名、IRI体系は公式API仕様を基準とする。

仕様で確認できない項目をRhinestone独自で発明しない。

---

## 8.5 Specとして保持する知識

［OdptAdapter］は最低限、

```text
resource type
operator
railway
station
direction
date/time semantics
identifier scheme
API endpoint
authentication method
response semantics
```

をProvider Specとして扱う。

---

## 8.6 Source

```text
Source
├ Metadata
│  ├ provider = ODPT
│  ├ transport operator
│  ├ resource type
│  └ raw metadata
├ Resource候補
└ Provenance
```

---

## 8.7 AccessPlan

ODPTはService型Sourceとして扱う。

```text
ServiceQueryPlan
```

基本とする。

Config → API Requestの変換は［OdptAdapter］の責務。

---

## 8.8 Temporal Data

公共交通データでは時刻や運行状態等、更新頻度が高いデータが存在する。

したがってProvenanceに、

```text
retrieved_at
provider timestamp
validity / update information
```

を可能な範囲で保持する。

---

## 8.9 Search

初期実装ではAPIが提供する検索・filter capabilityのみを利用する。

Rhinestone側で全文検索indexを構築しない。

---

## 8.10 Terms

ODPTには利用規約・基本ライセンス・開発者ガイドライン等が存在するため、関連Metadataを保持できること。citeturn862912search5

Rhinestoneは利用規約への適合性を自動保証しない。

---

# 9. ［Credential Registry］

今回のAdapter拡張に伴い、credential injectionの概念を正式に導入する。

これはGDAL等の［Dependency Registry］と同じ思想に基づく。

```text
Secret
  ↓
user callback
  ↓
［Credential Registry］
  ↓
［Source Adapter］
```

---

## 9.1 原則

Credentialは、

```text
Config
Source
Metadata
Provenance
```

へ平文で保存しない。

---

## 9.2 Config

Configにはlogical credential nameのみを記述する。

```yaml
credential: odpt
```

---

## 9.3 runtime

```python
Rhinestone(
    credentials={
        "odpt": lambda: os.environ["ODPT_API_KEY"],
        "gsi": lambda: load_gsi_credentials(),
    }
)
```

---

# 10. Spec Registry

［GSI Tile Adapter］等では、外部APIアクセスだけでなくRhinestone自身が保持する既知Specが重要になる。

そのため必要に応じて、

```text
［Spec Registry］
```

相当の内部概念を導入してよい。

ただし初期段階では独立コンポーネントとして公開する必要はない。

例えば、

```text
gsi tiles
PLATEAU format mappings
GSI schema versions
DEM types
```

等をAdapter内部データとして保持してよい。

---

# 11. Spec Dataと実装コードの分離

静的なProvider knowledgeは、可能な限りコードへ直接埋め込まず、宣言的データとして保持する。

例:

```yaml
id: std
title: Standard Map
scheme: xyz
format: png
min_zoom: 2
max_zoom: 18
```

ただし、YAML化そのものを目的としない。

条件分岐やProtocol処理まで無理にDSL化しない。

---

# 12. Adapter間の責務

## ［Source Adapter］

知るもの:

```text
Provider API
Provider identifiers
Provider metadata
Provider distribution structure
Provider authentication semantics
```

---

## ［Resolver］

知るもの:

```text
SourceからどのResourceを選ぶか
```

---

## ［Execution Adapter］

知るもの:

```text
ResourceをGDAL等でどう開くか
```

---

## ［Credential Registry］

知るもの:

```text
credential callback
```

Secretの意味やAPIへの付与方法は知らない。

---

# 13. Example追加

Adapter実装後、以下を追加する。

```text
examples/
├ gsi_tile.py
├ plateau_citygml.py
├ gsi_fundamental_dem.py
├ dcat_dataset.py
└ odpt_station.py
```

---

# 14. Example優先度

最初に以下を完成させる。

```text
1. gsi_tile.py
2. plateau_citygml.py
3. dcat_dataset.py
```

これらはアピール用として強い。

認証が必要な、

```text
gsi_fundamental_dem.py
odpt_station.py
```

はadvanced exampleとして扱う。

---

# 15. Tests

各Adapterについて最低限、

```text
Config validation
Metadata mapping
Resource generation
Provenance preservation
ambiguous resource handling
unsupported input handling
```

をcontract testする。

Provider-specific fixtureは公式仕様を確認した上で作成する。

---

# 16. Golden Test方針

以下の順序を守る。

```text
Official specification
      ↓
Rhinestone Adapter specification
      ↓
fixture
      ↓
golden test
      ↓
implementation
```

Exampleや実装の都合からfixture contractを逆算してはならない。

---

# 17. Live Tests

Scheduled CIで以下を監視可能とする。

```text
GSI Tile endpoint
PLATEAU distribution metadata
GSI Fundamental metadata/service
DCAT endpoint
ODPT API
```

認証必須ProviderについてはCI credentialがない場合skip可能とする。

---

# 18. 優先実装順

## Phase 1

```text
［StaticAdapter］
```

目的:

```text
認証不要
Spec-driven
地理空間用途が明確
README映え
Execution Adapter連携確認
```

---

## Phase 2

```text
［PlateauAdapter］
```

目的:

```text
日本固有
複数distribution
3D geospatial
Resource selection実証
```

---

## Phase 3

```text
［GsiFundamentalAdapter］
```

目的:

```text
versioned specification
CRS migration
schema knowledge
credential injection
```

---

## Phase 4

```text
［DcatAdapter］
```

目的:

```text
標準catalog
federated search
Dataset / Distribution mapping
国際互換性
```

---

## Phase 5

```text
［OdptAdapter］
```

目的:

```text
service-oriented source
credential
real-time / temporal data
GIS以外の公共データへの拡張
```

---

# 19. この拡張で証明すること

5 Adapterの実装により、Rhinestoneは以下を扱えることを実証する。

```text
Static File
CKAN Catalog
Statistical API
STAC
OGC
XYZ Tile
3D City Model
Versioned GML
RDF Catalog
Authenticated Transport API
```

つまり、

```text
「特定Provider用wrapper」
```

ではなく、

```text
「異なる公共データアクセス仕様を
  Knowledge / Specとして統合する層」
```

であることを示す。

---

# 20. 最終アーキテクチャ

```text
                        SearchQuery
                            ↓
                   ［Search Coordinator］
                            ↓
       ┌────────────────────┼────────────────────┐
       ↓                    ↓                    ↓
［StaticAdapter］  ［PlateauAdapter］       ...
［DcatAdapter］     ［OdptAdapter］
       │                    │
       └────────────────────┼────────────────────┘
                            ↓
                           Source
                            ↓
                       ［Resolver］
                            ↓
                        AccessPlan
                            ↓
                         Resource
                            ↓
              ［Execution Adapter Selector］
                            ↓
                 ［Execution Adapter］
                            ↓
                   user-owned runtime
```

認証が必要なSourceでは、

```text
user credential callback
          ↓
［Credential Registry］
          ↓
［Source Adapter］
```

が加わる。

---

# 21. 中心原則

このAdapter拡張でもRhinestoneの中心原則は変更しない。

> Rhinestoneはデータ処理エンジンを増やすのではなく、データを正しく扱うための知識を増やす。

したがって新しいProvider対応は、

```text
「何を実装できるか」
```

より先に、

```text
「何をSpecとして確定できるか」
```

を問う。

Rhinestoneは引き続き、

> Specを武器に戦うライブラリ

として設計する。