# 地理空間・公共データ統一アクセス基盤 仕様書 v0.2

## 1. 目的

本プロジェクトは、異なる配信元・配信方式・ファイル形式で提供される地理空間・公共データについて、利用者が配信元固有の詳細を意識せず、統一的な方法で取得できる軽量なOSSライブラリを提供することを目的とする。

本プロジェクトはデータを「探す」ためのライブラリではない。

利用対象となるデータセット、リソース、統計表、コレクション等は、ユーザーまたはAIによって事前に特定されていることを前提とする。

本ライブラリは、指定されたデータ参照を解釈し、配信元のメタデータを取得・検証し、適切なアクセス経路および既存OSSを決定して、実データへアクセスする。

基本的なユーザー体験は以下とする。

```text
Config
  ↓
指定済みData Reference
  ↓
Metadata取得
  ↓
Access Plan生成
  ↓
既存OSSへ委譲
  ↓
Data
```

設計思想を一文で表現すると、

> Reference in, usable data out.

である。

また、

> Different providers, same loading experience.

を利用体験上の目標とする。

---

# 2. スコープ

## 2.1 対象

初期段階では、日本国内で公開されている地理空間・統計・公共データを主対象とする。

初期Reference Implementationとして以下を想定する。

* CKAN
* GKAN
* e-Stat
* OGC API
* STAC
* 直接HTTP配布
* G空間情報センター
* PLATEAU

ただし、特定の日本政府機関に依存したCore設計にはしない。

---

## 2.2 明確にスコープ外とするもの

以下は本プロジェクトでは実装しない。

### Dataset Discovery

* 自然言語からDatasetを検索する
* CKAN package_searchで候補を探す
* e-Statの統計表を検索する
* 全国オープンデータをインデックスする
* データランキング
* 類似Dataset推薦

これらはユーザー、AI、既存カタログ、検索システムの責務とする。

### Catalog Site

* 全文検索
* Webポータル
* 巨大なDataset Registry
* データ一覧UI
* 検索ランキング

### GIS Viewer

* 地図表示
* データ可視化
* WebGIS UI

### データホスティング

公式データの再ホストを基本的に行わない。

### 汎用ETL

* 大規模Join
* 空間解析
* データ統合
* 高度な変換Pipeline

これらは既存OSSへ委譲する。

---

# 3. 設計原則

## 3.1 Existing OSS First

既存OSSで実現できる処理は再実装しない。

主な利用候補：

* GDAL
* pyogrio
* Rasterio
* GeoPandas
* PyArrow
* pandas
* fsspec
* Pooch
* OWSLib
* PySTAC
* pygeometa

---

## 3.2 Normalize Access, Not Data

データ形式を統一することを目的としない。

例えば、

```text
GeoPackage
GeoJSON
Shapefile
GeoTIFF
COG
Parquet
CSV
OGC API Features
```

を全て共通形式へ変換することはしない。

統一するのは、

```text
指定
↓
解決
↓
取得
```

というアクセス体験である。

---

## 3.3 Explicit over Magic

推測による暗黙処理を避ける。

原則：

```text
確実に判断できる
→ 自動処理

合理的に推測できる
→ warningまたは明示opt-in

判断できない
→ fail
```

---

## 3.4 Standards First

利用可能な場合は既存標準を優先する。

例：

* OGC API
* STAC
* DCAT
* CKAN API
* documented REST API
* GraphQL API
* GDAL対応形式

---

## 3.5 No Scraping

以下はCoreでは扱わない。

* HTML DOM解析
* CSS Selector
* XPath
* Headless Browser
* HTML Regex
* URL推測
* ダウンロードページ解析

machine-readableな正式インターフェースが存在しない場合は、原則として非対応とする。

---

## 3.6 Exitability

本プロジェクトへのlock-inを避ける。

以下を原則とする。

```text
No proprietary data format
No mandatory central server
No hidden transformation
No mandatory project-specific storage
```

本ライブラリが存在しなくなっても、Config・Metadata・URL・標準形式等から既存FOSS4Gを用いてアクセス経路を理解できることを目指す。

---

# 4. ユーザー向けメンタルモデル

利用者に見せる概念は可能な限り少なくする。

基本モデル：

```text
Config
  ↓
load()
  ↓
Data
```

必要に応じて、

```text
Config
  ↓
resolve()
  ↓
Access Plan
  ↓
load()
```

も利用できる。

内部で用いる複雑なProviderやAdapterの概念は、通常ユーザーには露出させない。

---

# 5. 内部アーキテクチャ

内部では以下の5段階を明確に分離する。

```text
Config
  ↓
DataReference
  ↓
SourceMetadata
  ↓
AccessPlan
  ↓
Execution
  ↓
Data
```

この責務境界をCore Architectureとする。

---

# 6. Config

ConfigはユーザーまたはAIが知っている事実のみを記述する。

ConfigはYAMLまたはJSONで表現可能とする。

YAMLを主なHuman-readable形式とする。

例：CKAN

```yaml
source:
  type: ckan
  endpoint: https://example.jp/api/3
  resource_id: abcdef
```

例：e-Stat

```yaml
source:
  type: estat
  stats_data_id: "0000000000"

query:
  area: "13101"
  time: "2025"
```

例：直接ファイル

```yaml
source:
  type: direct
  uri: https://example.jp/data.gpkg

data:
  format: geopackage
```

Configには実行結果を混ぜない。

Configは不変入力として扱う。

---

# 7. DataReference

DataReferenceは、

> 何を指しているか

だけを表現する。

どう読むか、どのDriverを使うかは持たない。

概念例：

```text
DataReference
├ CkanResourceReference
├ EstatTableReference
├ OgcCollectionReference
├ StacAssetReference
└ DirectResourceReference
```

例：

```text
CKAN
endpoint + resource_id

e-Stat
stats_data_id

OGC API
endpoint + collection_id

Direct
URI
```

DataReferenceはProvider固有の識別方式を表現する層である。

---

# 8. SourceMetadata

SourceMetadataは、

> 配信元が主張している事実

を表現する。

例：

* title
* license
* URL
* format
* media type
* protocol
* CRS
* geometry type
* bounding box
* temporal extent
* query dimensions
* available values

ConfigとMetadataは明確に分離する。

```text
Config
= user assertion

Metadata
= source assertion
```

元Metadataは可能な限りlosslessに保持する。

---

# 9. Metadataの扱い

## 9.1 Raw Metadata

配信元から得た元のMetadata。

原則として保持する。

---

## 9.2 Canonical Metadata

Resolverが必要とする最小限の共通情報。

巨大な共通Schemaへ完全正規化しない。

例：

```text
CanonicalMetadata
├ identifier
├ title
├ license
├ authority
├ resources
├ extent
└ provenance
```

---

## 9.3 Metadata Overlay

日本コミュニティ側で補足・修正・信頼情報を付与したい場合、元Metadataを書き換えずOverlayとして保持する。

例：

```yaml
trust:
  authority: official
  community_verified: true
```

---

## 9.4 Provenance

Metadata値がどこから得られたかを追跡可能にする。

将来的には、

```text
Raw
Derived
Overlay
Inherited
```

等の区別を持たせる。

---

# 10. Resolver

Resolverは本プロジェクトの中心的責務を持つ。

入力：

```text
DataReference
SourceMetadata
User Requirements
Environment Capabilities
```

出力：

```text
AccessPlan
```

Resolverは実データ内容を読まない。

Resolverはアクセス方法を決定するだけである。

---

# 11. Resolverの形式的定義

Resolverは理論上、以下の決定的関数として扱う。

```text
R:
Config × Metadata × Capabilities
→ AccessPlan | Error
```

同一の、

* Config
* Metadata
* Capability集合

に対しては、同一のAccessPlanを返すことを原則とする。

---

# 12. AccessPlan

AccessPlanは、

> 何を、どの方法で、どの既存OSSへ渡せばよいか

が完全に決まった状態を表す。

単純なResource URLだけには限定しない。

想定する型：

```text
AccessPlan
├ FileAccessPlan
├ RemoteDatasetPlan
└ ServiceQueryPlan
```

例：

CKAN GeoPackage

```text
FileAccessPlan
URI: https://...
format: geopackage
loader capability: vector.read
```

e-Stat

```text
ServiceQueryPlan
service: estat
stats_data_id: ...
query: ...
representation: json
```

OGC API Features

```text
RemoteDatasetPlan
protocol: ogc-api-features
endpoint: ...
collection: ...
loader capability: vector.read.remote
```

---

# 13. Capability

Resolverは特定ライブラリ名ではなく、Capabilityを基準に考える。

例：

```text
vector.read
raster.read
table.read
service.estat.query
ogc.features.read
```

Integration LayerがCapabilityを既存OSSへ割り当てる。

例：

```text
vector.read
→ pyogrio

raster.read
→ rasterio

table.read
→ pyarrow

ogc.features.read
→ GDAL / OWSLib
```

これによりResolverが特定実装へ依存することを防ぐ。

---

# 14. Execution

Execution層のみが実データを読む。

AccessPlanを既存OSSへ渡す。

例：

```text
FileAccessPlan
→ pyogrio

RemoteDatasetPlan
→ GDAL

ServiceQueryPlan
→ e-Stat API client
```

Loaderはデータ選択を行わない。

選択は必ずResolverで完了している必要がある。

---

# 15. Loader

Loaderは既存OSSへの薄い接続層とする。

初期候補：

```text
Vector
→ pyogrio / GDAL

Raster
→ Rasterio / GDAL

Table
→ PyArrow / pandas

STAC
→ PySTAC

OGC
→ GDAL / OWSLib
```

独自Readerは可能な限り作成しない。

---

# 16. Transport

Transport処理も既存OSSへ委譲する。

候補：

```text
GDAL VSI
fsspec
Pooch
```

原則：

```text
GDALが直接読める
→ 直接読む

汎用remote filesystem
→ fsspec

再現性・cache・checksumが必要
→ Pooch
```

---

# 17. Cache

Cacheは必須機能としない。

必要に応じて有効化可能とする。

保存候補：

* URL
* checksum
* timestamp
* ETag
* Last-Modified

---

# 18. Validation

Validationを段階的に分離する。

## 18.1 Config Validation

Config Schemaが正しいか。

JSON Schema等を使用する。

---

## 18.2 Reference Validation

DataReferenceとして十分な識別情報が存在するか。

---

## 18.3 Metadata Validation

Metadataが必要情報を含むか。

---

## 18.4 Resolution Validation

AccessPlanが構造上成立するか。

---

## 18.5 Capability Validation

実行環境に必要Capabilityが存在するか。

例：

```text
GeoPackage
↓
vector.read capability
↓
pyogrio/GDAL available
↓
VALID
```

---

## 18.6 Data Validation

必要に応じて実データについて、

* CRS
* geometry
* schema
* encoding

等を確認する。

---

# 19. plan()

実データ取得前にAccessPlanを確認可能とする。

例：

```text
Source:
CKAN resource abcdef

Metadata:
format = GeoPackage

Plan:
HTTP resource
→ GeoPackage
→ vector.read
→ pyogrio

VALID
```

e-Statの場合：

```text
Source:
e-Stat table 0000000000

Query:
area = 13101
time = 2025

Metadata:
area exists ✓
time exists ✓

Plan:
e-Stat API
→ JSON
→ table.read
→ DataFrame

VALID
```

---

# 20. CKAN / GKAN

CKANではデータ検索を行わない。

Configには対象Resourceが指定されていることを前提とする。

例：

```yaml
source:
  type: ckan
  endpoint: https://example.jp/api/3
  resource_id: abcdef
```

処理：

```text
resource_id
↓
CKAN API
↓
resource metadata
↓
Resource Descriptor
↓
AccessPlan
↓
Loader
```

GKANはCKAN profileとして扱うことを検討する。

```text
protocol = CKAN
profile = GKAN
```

GKAN専用実装を作る前に、CKAN共通処理で吸収可能か確認する。

---

# 21. e-Stat

e-Statでは統計表検索を行わない。

`stats_data_id` が指定されていることを前提とする。

例：

```yaml
source:
  type: estat
  stats_data_id: "0000000000"

query:
  area: "13101"
```

処理：

```text
stats_data_id
↓
getMetaInfo
↓
query validation
↓
ServiceQueryPlan
↓
getStatsData
↓
DataFrame
```

e-Statはformatではなくservice/protocolとして扱う。

---

# 22. OGC

OGC APIを標準的なRemote Dataset accessとして扱う。

OGC準拠をプロジェクト全体へ強制しない。

利用可能な場合に優先する。

例：

```text
OGC API Features
→ RemoteDatasetPlan
```

OWSLibはservice metadata/capability確認に利用できる。

GDALは実データアクセスに利用できる。

---

# 23. STAC

STACではItem/Assetが事前に特定されていることを前提とする。

STAC Catalog全体からのDiscoveryはスコープ外。

例：

```text
STAC Asset Reference
↓
Asset metadata
↓
href + media type
↓
AccessPlan
```

---

# 24. pygeometa / MCF

pygeometaおよびMCFはMetadata表現・変換・検証の既存OSSとして参考にする。

ただし、Core内部モデルをMCFへ完全依存させることは現時点では決定しない。

MCFは入力Metadata形式の一つとして扱える構造を目指す。

---

# 25. HydroMTとの関係

HydroMT DataCatalogを重要な先行実装として参考にする。

特に以下の責務分離を参考にする。

```text
DataSource
URIResolver
Driver
Metadata
```

今回の構造との対応：

```text
HydroMT URIResolver
≈ Reference/Resource resolution

HydroMT Driver
≈ Loader

HydroMT DataSource
≈ Reference + Metadata + Access config
```

ただしHydroMT自体への依存は必須としない。

HydroMT DataCatalog YAMLとの部分的互換性は検討対象とする。

実装互換より、

> catalog concept compatibility

を優先する。

---

# 26. Config互換性

HydroMTの単純なDataCatalog定義を参考にする。

例：

```yaml
some_data:
  uri: https://example.jp/data.gpkg
  data_type: GeoDataFrame
  driver:
    name: pyogrio
```

ただし本プロジェクトでは、よりsemanticな指定を優先する。

例：

```yaml
source:
  type: direct
  uri: https://example.jp/data.gpkg

data:
  type: vector
  format: geopackage
```

通常ユーザーにpyogrio等の実装名を書かせない。

---

# 27. 内部依存方向

依存方向を固定する。

```text
Domain
↑
Resolution
↑
Adapters / Integration
↑
External OSS
```

Domain層は以下を知らない。

* CKAN
* e-Stat
* GDAL
* pyogrio
* Rasterio

Resolverも可能な限り実装ライブラリ名を知らない。

---

# 28. 内部不変条件

以下をArchitecture Invariantsとする。

1. Configは実行結果によって変更されない。
2. DataReferenceは「何を指すか」だけを表す。
3. DataReferenceはLoader情報を持たない。
4. Metadataは配信元の事実と派生情報を区別する。
5. 元Metadataを不用意に破棄しない。
6. Resolverは実データ内容を読まない。
7. LoaderはResource選択を行わない。
8. Provider固有ロジックをDomain層へ漏らさない。
9. データ形式変換を暗黙に行わない。
10. Loader選択は説明可能である。
11. 同一Config・Metadata・Capability集合から同一AccessPlanが得られる。
12. 推測不能な状態ではfailする。
13. 検索・DiscoveryロジックをCoreへ導入しない。
14. HTML scrapingを導入しない。
15. 既存FOSS4Gが処理可能なものを再実装しない。

---

# 29. エラー設計

失敗理由は可能な限り型として区別する。

例：

```text
InvalidConfig
InvalidReference
MetadataUnavailable
MetadataInvalid
UnsupportedProtocol
UnsupportedFormat
CapabilityUnavailable
InvalidQuery
ResourceUnavailable
IntegrityError
```

曖昧な、

```text
RuntimeError
```

へ集約しない。

---

# 30. Plugin / 拡張性

v0.xでは高度なPlugin APIを先に設計しない。

初期は内部Registryでよい。

例：

```text
reference adapters:
- ckan
- estat
- ogc
- stac
- direct

loaders:
- vector
- raster
- table
```

複数の外部Contributorによる実装パターンが揃った段階でPython entry points等による正式Plugin APIを設計する。

原則：

> abstraction after repetition

とする。

---

# 31. 開発手法

本プロジェクトでは、

> Specification by Example + Contract Testing + Vertical Slicing

を基本とする。

---

# 32. Golden Cases

実装前に代表Configと期待結果を固定する。

初期候補：

```text
CKAN resource → GeoPackage
CKAN resource → zipped Shapefile
GKAN resource → GeoJSON
e-Stat table → JSON → DataFrame
OGC API Features → vector
STAC Asset → COG
Direct HTTP → GeoTIFF
```

各ケースについて、

```text
Input Config
Expected Metadata
Expected AccessPlan
Expected Loader Capability
Expected Result Type
```

を定義する。

---

# 33. Contract Test

重要な境界は以下とする。

```text
Config
↓
Reference

Reference
↓
Metadata

Reference + Metadata
↓
AccessPlan

AccessPlan
↓
Data
```

内部実装ではなく、各境界の契約をテストする。

---

# 34. Test Layer

## 34.1 Schema Test

Configが仕様に適合するか。

## 34.2 Resolution Test

期待するAccessPlanが生成されるか。

## 34.3 Loader Contract Test

AccessPlanから正しい既存OSSへ委譲できるか。

## 34.4 Live Integration Test

実際のCKAN、e-Stat、OGC等で動くか。

---

# 35. Offline / Live Test分離

PR CIではfixtureのみ利用する。

```text
PR CI
→ deterministic
→ offline
```

実サービスへの接続はscheduled CIで行う。

```text
scheduled CI
→ CKAN
→ e-Stat
→ OGC
→ STAC
```

外部サービス障害によって通常PRをfailさせない。

---

# 36. Fixture

外部Metadataレスポンスをfixtureとして保持する。

例：

```text
fixtures/
  ckan/
  estat/
  ogc/
  stac/
```

Provider追加時には、

```text
fixture
+
expected AccessPlan
+
contract test
```

を基本的なContribution単位とする。

---

# 37. 初期Vertical Slice

最初の実装対象：

```text
CKAN resource_id
↓
Metadata取得
↓
GeoPackage Resource
↓
AccessPlan
↓
pyogrio
↓
GeoDataFrame
```

次に、

```text
e-Stat stats_data_id
↓
Metadata取得
↓
Query Validation
↓
ServiceQueryPlan
↓
API
↓
DataFrame
```

を実装する。

この2系統を同じCore Architectureで扱えることを設計成立条件とする。

---

# 38. Reference Implementationの意味

GKAN/CKANとe-Statは異なるアクセスモデルを代表する。

```text
CKAN/GKAN
= Resource型

Metadata
↓
Resource URL
↓
Generic Loader
```

```text
e-Stat
= Service型

Metadata
↓
Query
↓
Service-specific Access
```

この2つを同一の、

```text
Config
→ Reference
→ Metadata
→ AccessPlan
→ Data
```

モデルで自然に表現できることを重要な設計検証とする。

---

# 39. 初期成功条件

v0.xでは以下を満たせばよい。

1. 指定済みCKAN Resourceを取得できる。
2. 指定済みe-Stat統計表を取得できる。
3. Discoveryを一切行わない。
4. 配信元ごとの差異をユーザーへ極力露出させない。
5. Configが機械的にValidationできる。
6. AccessPlanを取得前に確認できる。
7. Metadataの出自を保持できる。
8. HTML scrapingを必要としない。
9. 既存FOSS4Gへ実データ処理を委譲できる。
10. Coreが特定ProviderやLoader実装へ過度に依存しない。

---

# 40. プロジェクトの中心的型

現時点では、内部Domainの中心型を以下の4つとする。

```text
DataReference
SourceMetadata
AccessPlan
Capability
```

外部表現として、

```text
Config
```

実行側として、

```text
Loader
```

を持つ。

最終的な処理モデル：

```text
Config
  ↓ parse
DataReference
  ↓ inspect
SourceMetadata
  ↓ resolve
AccessPlan
  ↓ execute
Data
```

---

# 41. 一文定義

> 指定された地理空間・公共データ参照について、配信元固有のMetadataとアクセス方式を解釈し、適切な既存OSSへ解決することで、配信元の違いを意識せずデータへアクセスできる軽量なOSSライブラリ。

短縮表現：

> Config-driven public geospatial data resolver and loader.

さらに短く：

> Reference in, usable data out.
