# Rhinestone 仕様書 v0.4

## 1. 概要

Rhinestoneは、日本の公的・地理空間データを統一的に扱うためのPythonライブラリである。

Rhinestone自身がGISデータ処理エンジンを再実装することは目的としない。

本ライブラリの中心的な価値は、各データ提供元・API・フォーマット・配信方式について、

- どこにデータがあるか
- どのように参照するか
- どのようなメタデータを持つか
- どのResourceを選択すべきか
- どのような方法でアクセスすべきか
- GDAL、Rasterio、pyogrio等へどのように渡すべきか

という知識をSpecとして蓄積し、利用者に提供することにある。

Rhinestoneは、データ処理ライブラリというよりも、

> 公的・地理空間データのための Knowledge / Specification Layer

として位置付ける。

---

## 2. 表記規則

本仕様書では、データ／モデルと処理コンポーネントを区別するため、以下の表記を用いる。

### 2.1 データ／モデル

通常表記とする。

例:

```text
Config
Source
Metadata
AccessPlan
Resource
SearchQuery
SearchResult
Provenance
```

### 2.2 コンポーネント

処理を担当するコンポーネントは `［］` で囲う。

例:

```text
［Source Adapter］
［Resolver］
［Execution Adapter］
［Search Coordinator］
［Adapter Registry］
［Dependency Registry］
```

以降の図および説明ではこの表記に統一する。

---

## 3. 基本思想

### 3.1 Specを中心とする

Rhinestoneは処理能力そのものではなく、処理方法に関する知識を提供する。

例えば、

```text
format = shapefile
archive = zip
encoding = cp932
```

というResourceに対して、

```text
GDALならどのURIを構築するか
どのopen optionを使うか
どのファイルをentry pointとするか
```

をRhinestoneが知っている状態を目指す。

新しい対応を追加することは、

```text
新しい処理エンジンを実装する
```

ことではなく、

```text
Rhinestoneが理解できるSpecを増やす
```

ことと考える。

---

## 4. 設計原則

Rhinestoneは以下を基本原則とする。

1. Lightweight Core
2. Existing OSS First
3. Normalize Access, Not Data
4. Explicit Over Magic
5. Preserve Knowledge
6. User-Owned Runtime Dependencies
7. Fail Rather Than Guess
8. No Scraping in Core
9. Federated Search
10. FOSS4G Compatibility
11. No Mandatory Central Infrastructure
12. Specification-Oriented Design

---

## 5. Existing OSS First

Rhinestoneは既存OSSが担える機能を原則として再実装しない。

利用候補には以下が含まれる。

```text
GDAL
Rasterio
pyogrio
GeoPandas
PyArrow
fsspec
Pooch
OWSLib
PySTAC
pygeometa
```

Rhinestoneが担当するのは、

```text
何を
どこから
どのように取得し
どのOSSへ
どの設定で渡すべきか
```

という判断である。

実際のデータ読み込み・変換・解析処理は既存OSSへ委譲する。

---

## 6. 全体アーキテクチャ

基本的な処理フローを以下とする。

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
  ↓
［Execution Adapter Selector］
  ↓
［Execution Adapter］
  ↓
User-provided dependency
  ↓
GDAL / Rasterio / pyogrio / etc.
```

検索を利用する場合は、

```text
SearchQuery
  ↓
［Search Coordinator］
  ↓
［Source Adapter］群
  ↓
SearchResult[]
  ↓
Config
```

となる。

検索結果は直接データ取得処理へ流さず、Configへ変換したうえで通常の解決フローへ入れる。

---

## 7. Config

ConfigはRhinestoneへの宣言的な入力データである。

Configは、

> 何のデータを利用したいか

を記述する。

HTTP通信方法、GDALオプション等の内部実装詳細は原則として記述しない。

例:

```yaml
catalog:
  sources:
    geospatial-jp:
      adapter_type: ckan
      settings:
        endpoint: https://www.geospatial.jp/ckan
config:
  source_id: geospatial-jp
  settings:
    resource_id: abcdef
```

e-Statの場合:

```yaml
catalog:
  sources:
    estat:
      adapter_type: estat
      settings:
        endpoint: https://api.e-stat.go.jp/rest/3.0/app/json
        language: J
config:
  source_id: estat
  settings:
    stats_data_id: "0000000000"
```

Source固有の固定値はCatalogの`SourceDefinition.settings`が管理し、対象指定はConfigへ置く。

Configの`source_id`は`configure()`で構成済みのSourceDefinitionを参照する。
Source識別子と［Source Adapter］種別を同一視してはならない。同じAdapter種別を利用する
複数Sourceを同時に構成できなければならない。

Core側に巨大なprovider union schemaを持たせない。

---

## 8. ［Source Adapter］

［Source Adapter］は外部データ提供元とRhinestone Coreとの境界となるコンポーネントである。

例:

```text
［CkanAdapter］
［EStatAdapter］
［StacAdapter］
［OgcAdapter］
［DirectAdapter］
```

［Source Adapter］はprovider固有の知識を持つ。

例えばCKANであれば、

```text
resource_idの意味
package/resource構造
resource URLの取得方法
format情報
metadata構造
```

などを理解する。

e-Statであれば、

```text
statsDataId
統計表metadata
dimension
category
area
time
API query
```

などを理解する。

［Source Adapter］は外部providerを解釈し、Coreが理解できるSourceを生成する。

---

## 9. Adapter内部構造

初期段階では［Adapter］内部を過度に分割しない。

例えば、

```text
［CkanAdapter］
```

が内部でHTTP通信まで行ってよい。

以下のような分割は、実際に必要になった段階で行う。

```text
［CkanAdapter］
  ↓
［CkanClient］
```

Rhinestoneでは、

> ［Adapter］外部の責務境界を安定させ、内部は必要になるまで自由に保つ

方針を採用する。

---

## 10. Source

Sourceは［Source Adapter］によって解釈されたデータソースを表すモデルである。

Sourceはprovider固有Referenceそのものではない。

Provider固有Referenceは［Source Adapter］内部に閉じ込める。

Sourceは概念的に以下を含む。

```text
Source
├ Metadata
├ Resource候補
├ Capability情報
├ Provenance
└ source-specific raw metadata
```

Sourceは巨大な共通メタデータスキーマを目指さない。

必要最小限の共通項目と、元のMetadataを保持する。

---

## 11. Metadata

MetadataはRhinestoneの重要なデータ資産である。

取得過程で判明した情報は可能な限り保持する。

例:

```text
title
description
publisher
license
updated_at
resource_id
format
media_type
CRS
source URL
API endpoint
query parameters
provider metadata
```

RhinestoneはMetadataを過度に正規化しない。

共通Metadataに加えて、providerから得たraw metadataを保持できる構造とする。

pygeometa / MCF等との連携は、将来的なMetadata表現・変換手段として検討する。

---

## 12. Preserve Knowledge

Rhinestoneの重要な不変条件として、

> 一度Rhinestoneが確定した情報を、後続処理の都合で捨てない

ことを定める。

例えばCKAN Resourceを解決した結果、

```text
CKAN resource_id
dataset title
publisher
license
format
download URL
encoding
provenance
```

を得た場合、

単純に

```text
https://example.jp/data.zip
```

だけを返して情報を失ってはならない。

後続処理でもResourceを通して元の情報へアクセスできる必要がある。

---

## 13. ［Resolver］

［Resolver］はSourceから実際に利用可能なResourceまたはAccessPlanを決定するコンポーネントである。

［Resolver］はproviderとの通信処理そのものではなく、

```text
Sourceに含まれるResource候補のうち
どれを
どの方法で
利用するか
```

を判断する。

［Resolver］は原則としてデータ本体を読み込まない。

---

## 14. AccessPlan

AccessPlanは、

> Resourceへどのようにアクセスするか

を表現するモデルである。

データ提供方法によって異なるAccessPlanを扱えるようにする。

例:

```text
FileAccessPlan
RemoteDatasetPlan
ServiceQueryPlan
```

例:

```text
CKAN ZIP Shapefile
→ FileAccessPlan

COG
→ RemoteDatasetPlan

e-Stat API query
→ ServiceQueryPlan
```

AccessPlanは実際のOSSへの依存を持たない。

---

## 15. Resource

ResourceはRhinestoneによって解決された利用可能なデータ資源を表すモデルである。

概念的には以下を持つ。

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

Resourceは単なるURIではない。

Rhinestoneが取得・推論・確定した情報を保持する。

---

## 16. ［Execution Adapter］

［Execution Adapter］は、

> RhinestoneのResourceを既存OSSが理解できる形へ翻訳する

ためのコンポーネントである。

例:

```text
［GdalAdapter］
［RasterioAdapter］
［PyogrioAdapter］
［PyArrowAdapter］
```

［Execution Adapter］自身がデータ処理エンジンを実装するわけではない。

例えば［GdalAdapter］は、

```text
Resource
  ↓
GDAL URI
GDAL open options
layer/subdataset指定
```

への変換方法を知る。

つまり、

> GDALを所有するのではなく、GDALの使い方を知っている

コンポーネントである。

---

## 17. ［Execution Adapter Selector］

ユーザーが通常利用する際、［Execution Adapter］を毎回指定する必要はない。

［Execution Adapter Selector］がResourceの内容と利用可能な依存を見て、適切な［Execution Adapter］を選択する。

例:

```text
Resource
format = shapefile
archive = zip

available dependencies:
  gdal
  pyogrio

［Execution Adapter Selector］
→ ［GdalAdapter］または［PyogrioAdapter］を選択
```

必要に応じてユーザーが明示指定することも許可する。

```python
resource.open(adapter="gdal")
```

---

## 18. User-Owned Runtime Dependencies

GDAL、Rasterio、pyogrio等のruntime dependencyはRhinestoneが所有しない。

依存ライブラリのバージョン管理はユーザー環境側の責務とする。

例えば、

```text
User environment
├ GDAL 3.x
├ Rasterio
└ pyogrio
```

をRhinestone自身が固定依存として要求しない。

これにより、

```text
Rhinestoneが要求するGDAL
vs
ユーザーが必要とするGDAL
```

という依存衝突を避ける。

---

## 19. ［Dependency Registry］

Execution用runtime dependencyは［Dependency Registry］を介して管理する。

ユーザーはGDAL等の依存実体をcallback/factoryとして注入する。

概念例:

```python
rhinestone.configure(
    dependencies={
        "gdal": lambda: osgeo.gdal,
        "rasterio": lambda: rasterio,
    }
)
```

重要なのは、

> ユーザーが［Execution Adapter］を選択するのではない

という点である。

ユーザーが行うのは、

```text
この環境ではこのGDALを使ってよい
```

というdependencyの供給のみである。

［Execution Adapter］の選択はRhinestone側が行う。

---

## 20. Dependency Callback

dependencyをcallbackとして受け取ることで、以下を可能にする。

```text
lazy import
optional dependency
user-controlled version
custom initialization
mock injection
test dependency
environment-specific loading
```

［Execution Adapter］は必要になった段階で［Dependency Registry］からcallbackを取得して呼び出す。

概念的には、

```python
gdal = dependencies["gdal"]()
```

となる。

Rhinestone Coreが直接、

```python
import osgeo.gdal
```

することは避ける。

---

## 21. ［Execution Adapter］の責務

例えば以下のResourceがあるとする。

```text
format = shapefile
archive = zip
encoding = cp932
```

［GdalAdapter］は、

```text
ZIPである
Shapefileである
文字コード情報がある
```

というRhinestone側の知識から、

```text
適切な /vsizip/ URI
open option
layer指定
```

等を構築する。

Rasterの場合も同様である。

```text
COG
→ remote access

GeoTIFF
→ direct/local access

NetCDF
→ subdataset

WMS
→ service access
```

この判断知識が［Execution Adapter］の価値となる。

---

## 22. ［Search Coordinator］

Rhinestoneは複数［Source Adapter］を横断した検索を提供できる。

ただし中央検索インデックスは原則として持たない。

```text
SearchQuery
   ↓
［Search Coordinator］
   ├ ［CkanAdapter］.search()
   ├ ［EStatAdapter］.search()
   ├ ［StacAdapter］.search()
   └ ［OgcAdapter］.search()
   ↓
SearchResult[]
```

各providerが提供する公式APIを利用する。

---

## 23. Search Capability

すべての［Source Adapter］がsearchを実装する必要はない。

検索可能な［Source Adapter］のみがsearch capabilityを提供する。

検索条件にはprovider差があるため、共通SearchQueryは必要最小限とする。

候補:

```text
text
bbox
time
limit
```

各［Source Adapter］は対応可能な検索条件のみを処理する。

未対応条件を黙って無視しない。

---

## 24. SearchResult

SearchResultは検索結果を表すデータモデルである。

最低限以下を含む。

```text
SearchResult
├ title
├ description
├ source_id
├ provider-specific configuration
├ Metadata
└ Provenance
```

検索結果からfetchする場合、一度Configへ変換して通常のフローへ戻す。

```text
SearchResult
  ↓
Config
  ↓
［Source Adapter］
  ↓
Source
```

検索結果が検証処理をバイパスしてはならない。

---

## 25. Search Ranking

Provider固有のranking scoreを直接比較しない。

例えば、

```text
CKAN score = 10
STAC score = 0.8
```

を同一尺度として扱わない。

初期実装では、

```text
providerごとに結果を保持
```

する。

必要になれば、

```text
exact title match
official provider
metadata completeness
```

など共通信号によるrerankingを［Search Coordinator］へ追加する。

---

## 26. No Scraping

Coreの［Source Adapter］ではHTML scrapingを行わない。

禁止対象:

```text
DOM parsing
CSS selector
XPath
headless browser
HTML regex
download URL guessing
```

利用するもの:

```text
CKAN API
STAC API
OGC API
DCAT
documented REST API
GraphQL API
direct resource URL
official machine-readable metadata
```

公式machine-readable interfaceが存在しない場合は、

```text
unsupported
```

として扱うことを基本とする。

---

## 27. データ正規化

Rhinestoneはすべてのデータを単一形式へ変換しない。

例えば、

```text
GeoDataFrame
GeoJSON
Arrow
xarray
```

への強制変換は行わない。

Rhinestoneが統一するのは、

> データへのアクセス方法

であり、

> データそのもの

ではない。

---

## 28. GeoPandas等との関係

GeoPandasは必須依存としない。

同様に、

```text
GDAL
Rasterio
pyogrio
PyArrow
```

もCoreの必須依存とはしない。

利用者はResourceを直接利用してもよい。

```python
resource.uri
resource.metadata
resource.provenance
```

必要な場合のみ［Execution Adapter］を通して外部ライブラリへ接続する。

---

## 29. Provenance

Provenanceは取得・解決経路を表すデータである。

Rhinestoneは可能な限り以下を保持する。

```text
provider
dataset identifier
resource identifier
API endpoint
original URL
query parameters
retrieved_at
checksum
adapter
adapter version
raw metadata
```

これにより、

```text
どこから
いつ
どの条件で
どのResourceを取得したか
```

を後から確認できるようにする。

---

## 30. Reliability

Rhinestoneの信頼性は、

```text
有名なサイトだから信用する
```

というモデルではなく、

```text
検証可能
再現可能
失敗を明示する
```

というモデルとする。

原則:

```text
schema validation
semantic validation
explicit resource selection
checksum where applicable
provenance preservation
no silent fallback
```

を重視する。

---

## 31. Fail Rather Than Guess

不確かな場合にRhinestoneが勝手に推測して処理を継続しない。

```text
certain
→ automate

heuristic
→ explicit warning / opt-in

unknown
→ fail
```

を基本とする。

---

## 32. Testing

テストは大きく2種類に分ける。

### 32.1 Deterministic Tests

PR CIではネットワークに依存しないfixtureを利用する。

```text
CKAN fixture
e-Stat fixture
STAC fixture
OGC fixture
```

golden file / contract testを重視する。

### 32.2 Live Tests

scheduled CIでは実際の外部providerへアクセスする。

```text
CKAN live
e-Stat live
STAC live
OGC live
```

外部API変更を検出する目的で利用する。

---

## 33. HydroMTとの関係

HydroMT DataCatalogは重要な先行設計として参照する。

参考にするもの:

```text
declarative DataCatalog
DataSource
Driver
URIResolver
metadata separation
extension architecture
conformance tests
```

ただし、

```text
HydroMT dependency
完全なplugin compatibility
HydroMT内部型
hydrology固有設計
```

は継承しない。

必要であればHydroMT DataCatalog YAMLの単純なsubsetについて概念互換性を検討する。

RhinestoneはHydroMTのforkではなく、設計上のprior artとして扱う。

---

## 34. MapLibre的設計思想

Rhinestoneは実装互換よりSpecification互換を重視する。

これは、

```text
Mapbox実装をforkする
```

のではなく、

```text
style specificationを理解してMapLibreが実装する
```

という考え方に近い。

Rhinestoneも、

```text
provider implementation
```

そのものを抱えるのではなく、

```text
provider / format / access specification
```

を蓄積していく。

---

## 35. FOSS4Gとの統合

Rhinestoneは既存FOSS4G ecosystemの入口になることを目指す。

```text
Rhinestone
   ↓
Resource
   ↓
［Execution Adapter］
   ├ GDAL
   ├ QGIS
   ├ Rasterio
   ├ pyogrio
   ├ GeoPandas
   ├ DuckDB
   └ other tools
```

Rhinestone独自形式への変換を要求しない。

---

## 36. QGIS

QGIS 3系からも利用可能な設計を維持する。

特に、

```text
Python version
GDAL version
Qt/QGIS bundled dependencies
```

との競合を避けるため、Coreは外部runtime dependencyを固定しない。

QGIS環境のGDAL等を［Dependency Registry］へcallbackとして注入できることが望ましい。

これによりQGISが保持するruntimeをそのまま利用できる。

---

## 37. ［Adapter Registry］

［Source Adapter］および［Execution Adapter］の登録状態は［Adapter Registry］が管理する。
［Adapter Registry］は内部実装であり、利用者はAdapter instanceを登録しない。

Composition Rootは、Catalogから読み込んだ`SourceDefinition.adapter_type`から組み込み
［Source Adapter］を生成し、利用者が供給したdependencyに対応する組み込み
［Execution Adapter］を構成する。Source側はAdapter種別ではなく`source_id`で索引する。
Catalogは接続先や公式サービス仕様を宣言し、secretやruntime instanceは保持しない。
`rhinestone.sources`はCatalogから生成された組み込みSourceDefinitionを公開するfacadeである。

初期段階では複雑なplugin systemを必須としない。

Builtin Adapter:

```text
Source:
  ［CkanAdapter］
  ［EStatAdapter］
  ［StacAdapter］
  ［OgcAdapter］
  ［DirectAdapter］

Execution:
  ［GdalAdapter］
  ［RasterioAdapter］
  ［PyogrioAdapter］
```

将来的に必要になった場合のみPython entry point等による外部Adapter追加を検討する。

---

## 38. 用語

本プロジェクトでは原則として「Plugin」という用語を使用しない。

外部システムとの差異を吸収するコンポーネントをAdapterと呼ぶ。

```text
［Source Adapter］
［Execution Adapter］
```

に統一する。

---

## 39. Coreが直接知るべきでないもの

Coreは以下を直接知るべきではない。

```text
CKAN package JSON structure
e-Stat API request details
GDAL module location
Rasterio version
QGIS bundled GDAL
HTML DOM
provider-specific authentication implementation
```

これらは［Adapter］またはユーザー環境側の責務とする。

---

## 40. Coreが扱う主要データ

Coreは以下を主要なデータ／モデルとして扱う。

```text
Config
Source
Metadata
AccessPlan
Resource
Provenance
SearchQuery
SearchResult
```

---

## 41. Coreを構成する主要コンポーネント

Core周辺では以下のコンポーネントを扱う。

```text
［Source Adapter］
［Resolver］
［Search Coordinator］
［Execution Adapter Selector］
［Execution Adapter］
［Adapter Registry］
［Dependency Registry］
```

この一覧はデータモデルとは明確に区別する。

---

## 42. 主要な不変条件

Rhinestoneの設計上、以下を守る。

1. Configは実行によって暗黙に変化しない。
2. Provider固有ReferenceをCore Domainへ漏らさない。
3. ［Source Adapter］が外部provider差異を吸収する。
4. Sourceには解釈済み情報とraw metadataを保持できる。
5. ［Resolver］はデータ本体を原則読み込まない。
6. ［Execution Adapter］はResourceの選択を行わない。
7. ［Execution Adapter］は既存OSSの利用方法を知る。
8. 外部runtime dependencyはユーザーが所有する。
9. Rhinestone CoreはGDAL等を直接importしない。
10. 一度確定したMetadata / Provenanceを捨てない。
11. 暗黙のformat変換を行わない。
12. 未知の状況では推測よりfailureを選ぶ。
13. HTML scrapingをCoreへ持ち込まない。
14. 検索は中央indexではなくfederated方式とする。
15. SearchResultは通常のvalidation / resolutionフローを迂回しない。
16. 同一Config・Metadata・利用可能なCapabilityから同一AccessPlanが得られることを目指す。
17. Runtime dependencyのversion管理をRhinestoneが支配しない。
18. 新機能は「処理実装」より「Spec / Knowledge追加」として設計できないかを先に検討する。

---

## 43. Rhinestoneの責務境界

最終的な責務を以下のように定義する。

```text
Rhinestoneが所有するデータ／知識
--------------------------------
Config interpretation
Source
Metadata
AccessPlan
Resource
Provenance
provider knowledge
format knowledge
access specification

Rhinestoneが所有するコンポーネント
----------------------------------
［Source Adapter］
［Resolver］
［Search Coordinator］
［Execution Adapter Selector］
［Execution Adapter］
［Adapter Registry］
［Dependency Registry］

ユーザーが所有するもの
----------------------
GDAL runtime
Rasterio runtime
pyogrio runtime
QGIS runtime
dependency versions
application-specific processing

既存OSSが所有するもの
---------------------
file parsing
GIS IO
raster/vector processing
format conversion
data analysis
```

---

## 44. Rhinestoneの本質

Rhinestoneの本質は、

```text
万能なデータ処理ライブラリ
```

ではない。

また、

```text
巨大なデータカタログ
```

でもない。

Rhinestoneは、

> 異なる公的データ提供元と既存OSSの間に存在する「知識の断絶」をSpecによって埋めるライブラリ

である。

Rhinestoneが成長するとは、

```text
コード量が増えること
```

ではなく、

```text
正しく理解できるデータ提供元
正しく理解できるResource
正しく生成できるAccessPlan
正しく接続できる既存OSS
```

が増えることを意味する。

そのため、Rhinestoneは、

> Specを武器に戦うライブラリ

として設計する。
