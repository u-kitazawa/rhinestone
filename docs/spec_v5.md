# Rhinestone 仕様書 v0.5

> **文書ステータス: 移行先の設計草案。** Rhinestoneはこの設計へ段階的に移行中です。未実装または現在と異なるAPI例を含むため、現行の公開契約には[利用者向けガイドとAPIリファレンス](documentation-status.md)を使用してください。
>
> e-Stat 統計表 API（`EStatAdapter`、`estat-api`、`pyestat` 経路）は #56 の決定により現行契約から削除されています。この文書内の e-Stat 記述は履歴上の設計案です。

## 1. 概要

Rhinestone は、日本の公的・地理空間データを **探し、利用可能な Resource へ解決し、既存の専門ライブラリへ渡すための Python SDK** である。

日本の公共データでは、データ本体を読む前に次のような作業が発生する。

```text
提供元を調べる
→ catalog / API を検索する
→ dataset / distribution / asset を選ぶ
→ 自治体・年度・識別子・query を解決する
→ ZIP / Excel / GML / API 等の配布仕様を確認する
→ credential を適用する
→ 適切な Python ライブラリへ渡す
```

Rhinestone は、この「データを使える状態にするまで」の差異を吸収する。

利用者に見せる基本フローは次の 3 語を中心とする。

```text
search → resolve → open
```

ただし検索は必須ではない。

```text
search → Result → resolve → Resource → open
Config        → resolve → Resource → open
```

Rhinestone の中心は `resolve()` であり、検索は Resource を特定するための入口の一つである。

本仕様では Rhinestone を、汎用データフレーム、GIS 処理エンジン、巨大 catalog、独自 protocol client として設計しない。

> 日本の公共データに固有の識別・時点・空間・配布・provider の差異を、再現可能で利用可能な Resource へ解決する Knowledge / Resolution Layer

として位置付ける。

---

## 2. 目的

Rhinestone の目的は、日本の公共データ利用に残っている provider 固有の摩擦を、モダンで小さな Python API の裏側へ押し込むことである。

特に次を対象とする。

- provider / catalog ごとの検索方法
- provider 固有 identifier
- dataset から distribution / asset / archive member への解決
- 日本の自治体・地域コード・地域メッシュ等の地理的 identity
- 西暦 / 和暦 / 暦年 / 年度 / 調査時点等の時間表現
- 日本で頻出する encoding、ZIP、Excel、GML 等の配布慣習
- 元 provider、横断 catalog、実 Resource の provenance
- credential と access specification の分離
- Resource を適切な既存ライブラリへ渡す方法

利用者が provider の API 仕様やファイル配布慣習を知っていることを前提にしない。

---

## 3. 非目標

Rhinestone は以下を目的としない。

```text
独自 GIS engine
独自 DataFrame / Raster / Vector model
format conversion framework
rasterize / spatial join / aggregation / analysis
workflow engine
LLM orchestration framework
独自全文検索 engine
国内 dataset metadata の大量 harvesting / rehosting
独自 STAC / CKAN / e-Stat protocol client の再実装
```

既存 OSS が正しく担当できる処理は既存 OSS へ委譲する。

---

## 4. 設計原則

Rhinestone は以下を基本原則とする。

1. **Resolve First** — 中心責務は利用可能な Resource への解決である
2. **Japan-Aware, Not Category-Driven** — 日本固有知識を持つが、人口・交通・防災等のテーマ分類を Core に持ち込まない
3. **Existing OSS First** — protocol / runtime の成熟した実装を再実装しない
4. **Normalize Access, Not Data** — データ型を統一せず、アクセス方法を統一する
5. **Preserve Knowledge** — 解決過程で得た metadata / provenance / identifier を捨てない
6. **Fail Rather Than Guess** — 根拠のない URL、コード、format、archive member 等を推測しない
7. **Federated, Not Centralized** — 既存 catalog / provider API を upstream として利用し、中央 index を必須にしない
8. **Portable Resolution** — credential や runtime instance を除く解決情報は持ち運べる設計を目指す
9. **Thin Public API** — 内部知識が増えても通常利用者の API を肥大化させない
10. **No Scraping in Core** — 公開 API、公式 metadata、静的仕様を優先し、HTML scraping を Core の前提にしない
11. **No Transformation Pipeline** — `open()` 後の解析・変換は下流ライブラリの責務とする
12. **Provider Knowledge Is the Product** — 対応 Source を増やすことは provider 知識と解決能力を増やすことである

---

## 5. 公開メンタルモデル

通常利用者が理解すべき中心概念は少なく保つ。

```text
Source / Provider
Result
Resource
```

操作は以下を中心とする。

```python
app.search(...)
app.resolve(...)
resource.open(...)
```

`Config` は検索なしで確定した対象を指定するための宣言的入力として維持するが、検索フローで利用者に毎回意識させる必要はない。

`Source`, `ResourceCandidate`, `AccessPlan`, `Resolver`, Adapter Registry 等は、実装・拡張 API では重要でも、通常ユーザー向けの最初の説明には出さない。

---

## 6. 2つの入口

### 6.1 検索から始める経路

何を使うべきかまだ確定していない場合は検索から始める。

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
  ↓
resolve()
  ↓
Resource
```

例:

```python
results = app.search(SearchQuery(text="河川", limit=5))
resource = app.resolve(results[0].to_config())
```

公開 API は将来 `app.resolve(result)` 等へ簡略化してよい。内部的に `SearchResult → Config → Resource` の経路を維持することは妨げない。

### 6.2 決定的なConfig指定の経路

利用する provider / dataset / identifier が既に分かっている場合は検索を通さない。

```text
Config
  ↓
resolve()
  ↓
Resource
```

この経路は、再現可能な本番処理、テスト、固定された分析 pipeline に重要である。

探索時に search を使い、対象が確定した後は Config を固定する使い方を正式に認める。

---

## 7. Config（設定）

Config は、Rhinestone に対して「何を利用したいか」を宣言する入力である。

```python
Config(
    source_id="estat",
    settings={
        "stats_data_id": "...",
    },
)
```

Config には原則として以下を入れない。

```text
HTTP transport instance
runtime object
secret / API keyそのもの
GDAL等の実行オブジェクト
```

Source 固有の固定値は `SourceDefinition` 側、対象固有の指定は Config 側に置く。

Config は検索なしで直接構築可能でなければならない。

---

## 8. SourceDefinition と Source Catalog

Rhinestone の catalog は、国内 dataset を全件保持する巨大 index ではない。

Catalog に持つ主なものは、検索・解決の入口となるサービスまたは provider の定義である。

例:

```text
e-Stat
GSI
G空間情報センター
PLATEAU
ODPT
search.ckan.jp
STAC endpoint
ユーザー定義 CKAN / STAC / OGC endpoint
```

`SourceDefinition` は概念的に以下を表す。

```text
SourceDefinition
├ id
├ adapter_type
└ settings
```

同じ adapter type で複数 endpoint を構成できなければならない。

Rhinestone は dataset metadata を再収集・再ホストするのではなく、既存の catalog / provider API を upstream として利用する。

---

## 9. Discovery Source と Resolution Target

v0.5 では、検索した Source と最終的に Resource を解決する Source が同一であるという前提を置かない。

典型例:

```text
search.ckan.jp
  ↓ discovery
SearchResult
  ↓ target Config
自治体 CKAN / direct / actual provider
  ↓ resolve
Resource
```

したがって `SearchResult` は概念的に次を表現できなければならない。

```text
SearchResult
├ title
├ description
├ discovered_by
├ target Config
├ Metadata
└ Provenance
```

`SearchResult.to_config()` は target Config を返す。

互換性のために `source_id` / `settings` を公開する場合でも、それらは「検索を実行した Source」ではなく「resolve 先」を意味することを明確にする。

検索 catalog の provenance と元データ provider の provenance は失ってはならない。

---

## 10. 複数提供元の検索

Rhinestone の search は中央 index を前提とせず、構成済み Source へ問い合わせる federated search を基本とする。

### 10.1 SearchQuery（検索条件）

Core の公開 SearchQuery は必要最小限に保つ。

```text
text
bbox
time
limit
```

日本特化のために、公開 API へ以下のような引数を無制限に追加しない。

```text
prefecture
municipality
fiscal_year
mesh
survey_year
plateau_city_code
...
```

必要な日本固有解釈は内部の search context / provider translation で扱う。

### 10.2 対応条件に合わせた検索条件の投影

各 Source は、自身が理解できる検索条件だけを受け取る。

```text
SearchQuery(text, bbox, time)
  ├─ e-Stat -> text / 対応可能なtime
  ├─ STAC   -> bbox / time
  ├─ CKAN   -> text
  └─ 横断catalog -> text
```

1つの Source が条件に対応していないことを理由に、検索全体を失敗させてはならない。

概念的には次の投影を行う。

```text
ProviderQuery = SearchQuery × SourceCapabilities
```

unsupported condition は Source ごとに無視・skip・diagnostic として扱う。どの条件が実際に適用されたかを診断可能にすることが望ましい。

ただし、条件を無視したことで意味のない全件検索になる場合、Adapter はその Source 自体を skip できる。

### 10.3 提供元を限定した検索

特定 Source のみを検索する経路を許容する。

これは STAC の bbox 検索や特定 catalog の探索等で有用である。

公開 API の厳密な引数形状は実装時に決定してよいが、Core semantics として Source scope を妨げてはならない。

---

## 11. 日本固有の共有知識

Rhinestone は日本に特化するが、テーマ別 taxonomy は作らない。

```text
× PopulationCategory
× DisasterProvider
× TransportCatalog
× JapaneseDataOntology
```

のような分類体系を Core の中心に置かない。

代わりに、provider をまたいで再利用できる **横断的な解決知識** を持つ。

### 11.1 識別情報（Identity）

「これは何か」を解決する。

例:

```text
自治体名
都道府県・市区町村コード
同名自治体
旧自治体・廃置分合
標準地域コード
```

例:

```text
"新宿区"
  ↓
canonical municipality identity
  ↓
13104
```

### 11.2 空間情報（Space）

「どこか」を解決する。

例:

```text
行政区域
地域メッシュコード
bbox
JGD2000 / JGD2011 / JGD2024
平面直角座標系
高さ・測地基準
```

### 11.3 時間情報（Time）

「いつか」を解決する。

例:

```text
西暦 / 和暦
暦年 / 年度
survey year
as-of date
```

`令和2年` と `2020年度` を無条件に同一視しない。

### 11.4 データ形式（Representation）

日本の公的データで頻出する配布上の表現を理解する。

例:

```text
CP932 / Shift-JIS
UTF-8 BOM
日本語 ZIP filename
Excel
CSV
GML
先頭ゼロ付きコード
全角・半角等の表記差
```

ここで「理解する」ことと「勝手に変換する」ことを区別する。

Rhinestone は必要な encoding / entry point / access hint を Resource へ保持できるが、データ内容の transformation を Core の責務にはしない。

### 11.5 出典情報と方針（Provenance / Policy）

以下を区別する。

```text
検索した catalog
元 provider
publisher
元 dataset
実 distribution / asset
mirror / index
license / attribution
データ基準日
catalog updated_at
```

同じデータが複数 catalog で見つかった場合、可能な範囲で origin を保持し、別データとして不必要に重複させない設計を目指す。

---

## 12. Shared Japan Knowledge と Provider Adapter の境界

共有知識には、複数 provider で意味が安定しているものだけを置く。

例:

```text
"新宿区" -> canonical municipality identity
```

は共有知識である。

一方、

```text
canonical municipality -> e-Stat area parameter
canonical municipality -> PLATEAU dataset
```

は各 Provider Adapter の責務である。

同様に、

```text
令和2年 -> 2020 calendar year
```

は共有可能だが、

```text
2020 -> e-Stat time dimension code
```

は e-Stat 固有知識である。

この境界により、巨大な日本知識クラスや ontology を作らずに、日本特化能力を再利用できる。

---

## 13. ［Source Adapter］（提供元アダプター）

［Source Adapter］は provider / catalog と Rhinestone Core の境界である。

例:

```text
［EStatAdapter］
［CkanAdapter］
［StacAdapter］
［PlateauAdapter］
［OgcApiFeaturesAdapter］
［OdptAdapter］
［DirectAdapter］
```

Adapter は以下の一部または全部を担当できる。

```text
discovery
inspection
resolution
provider-specific query translation
metadata interpretation
```

すべての Adapter が search と resolve の両方を実装する必要はない。

概念的な capability として少なくとも以下を区別できる設計を許容する。

```text
search
resolve
```

横断 catalog は discovery-only でもよい。

---

## 14. 専門ライブラリへの委譲

v0.5 では、provider / protocol 固有 semantics を自前再実装するより、成熟した専門ライブラリを積極的に利用する。

例:

```text
e-Stat -> pyestat
STAC -> pystac-client / pystac
DCAT / RDF -> rdflib
Raster -> Rasterio / GDAL
Vector -> pyogrio / GDAL
PLATEAU -> plateaukit（適合性を確認した範囲）
```

専門ライブラリの採用基準は次とする。

- provider / protocol 固有仕様を相当量再実装せずに済む
- metadata / query / pagination / model semantics 等を正しく扱える
- 保守されておりライセンス・Python互換性が許容できる
- Rhinestone の Resource resolution と責務が完全重複しない

単純な HTTP request や少量の metadata extraction のためだけに依存を増やす必要はない。

### 14.1 e-Stat（統計データ）

pyestat は単なる Execution runtime に限定せず、e-Stat provider specialist として利用してよい。

概念フロー:

```text
SearchQuery
  ↓
［EStatAdapter］
  ↓ pyestat.list_stats / equivalent
SearchResult
  ↓
inspection / resolution
  ↓ pyestat.get_meta_info / equivalent
Resource(format="estat-api")
  ↓
open()
  ↓ pyestat.get_stats_data / equivalent
native statistical object
```

重要なのは、pyestat の型を Rhinestone の検索 API 全体へ漏らすことではなく、e-Stat semantics の実装を専門ライブラリへ委譲することである。

### 14.2 STAC（衛星画像等のカタログ）

STAC の conformance、pagination、extensions、Item / Asset semantics 等は、可能な範囲で pystac-client / pystac へ委譲する。

Rhinestone は STAC の再実装ではなく、検索結果から利用対象 asset を Resource として解決し、provenance を保つ。

---

## 15. Source（解釈済み情報）

Source は、［Source Adapter］が Config を解釈した結果として Core へ渡す内部モデルである。

概念的には以下を持つ。

```text
Source
├ Metadata
├ ResourceCandidate[]
├ capabilities
├ Provenance
└ raw metadata
```

Source は公開ユーザーが最初に理解すべき概念ではない。

Provider 固有の巨大 schema を共通 Source へ押し込まない。

---

## 16. ResourceCandidate と ［Resolver］

ResourceCandidate は、provider から見つかった利用候補である。

［Resolver］は候補から、実際に利用する Resource と access specification を確定する。

典型例:

```text
CKAN Dataset
  -> ResourceCandidate[]
  -> distribution selection
  -> Resource

STAC Item
  -> Asset[]
  -> data asset selection
  -> Resource

PLATEAU Dataset
  -> ZIP / package
  -> entry point selection
  -> Resource
```

［Resolver］は変換・分析エンジンではない。

判断基準は次とする。

> 宣言された Resource を意味的に同一のまま利用可能にするために必要な処理は resolution / access に含める。分析目的のために別の表現を作る処理は transformation とし、Core から除外する。

---

## 17. AccessPlan（アクセス方法）

AccessPlan は、解決済み Resource へアクセスするための仕様である。

例:

```text
FileAccessPlan
RemoteDatasetPlan
ServiceQueryPlan
```

AccessPlan は検索や分析を表現しない。

含めてよいもの:

```text
URI
archive type
entry point
open options
service query
response type
non-secret request parameters
```

含めないもの:

```text
credential value
runtime instance
analysis instruction
conversion pipeline
```

AccessPlan が単なる driver args の再包装にしかならない場合は、その抽象化の価値を再評価する。

---

## 18. Resource（利用するデータ）

Resource は Rhinestone によって解決された、利用可能な具体的データ資源である。

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

Resource は単なる URL ではない。

例えば、CKAN で発見した ZIP Shapefile について、Rhinestone が以下を知ったならそれを保持する。

```text
元 catalog
元 dataset / resource identifier
publisher
license
original URL
format
archive
entry point
encoding
query / selection provenance
```

最終的に `https://.../data.zip` だけへ縮退してはならない。

---

## 19. 持ち運び可能なResource仕様

v0.5 では Resource の runtime-bound 部分と、持ち運び可能な解決仕様を分離できる方向を採る。

概念:

```text
resolve()
  ↓
Resource specification
  ├ identity
  ├ metadata
  ├ provenance
  ├ access specification
  └ runtime requirement

Application context
  ↓ bind
Resource
  ↓ open
```

以下は portable specification に含めない。

```text
secret credential
live runtime instance
callable opener
process-local object
```

JSON round-trip、MCP、別 process、Intake export 等は、この境界の上に構築できる。

ただし v0.5 で専用 lockfile や新しい公開 `ResourceSpec` 型を必須とはしない。まず既存 Resource / AccessPlan の境界が portable になることを優先する。

---

## 20. Metadata と Provenance

Metadata と Provenance は Rhinestone の主要な価値である。

### 20.1 Metadata（メタデータ）

共通項目は必要最小限にする。

例:

```text
title
description
publisher
license
updated_at
format
media_type
```

provider metadata は raw form でも保持できる。

### 20.2 Provenance（出典情報）

少なくとも以下を可能な範囲で保持する。

```text
provider
dataset identifier
resource identifier
API endpoint
original URL
query parameters
retrieved_at
adapter / adapter version
```

横断 catalog から発見した場合、

```text
discovered through
origin catalog / provider
actual distribution
```

の関係を失わない。

`catalog updated_at` と `data temporal coverage / survey year` を同一視しない。

---

## 21. `open()` と ［Execution Adapter］

`open()` は解決済み Resource を既存ライブラリへ渡し、そのライブラリの自然なオブジェクトを返す。

例:

```text
COG -> Rasterio DatasetReader
vector file -> pyogrio / GDAL native result
estat-api -> pyestat native response
JSON service -> list / dict 等
```

Rhinestone 独自の共通 DataFrame / Raster 型へ強制変換しない。

［Execution Adapter］は、Resource を runtime が理解できる引数・URI・options へ翻訳する。

Execution Adapter の chaining は Core に導入しない。

1つの Adapter が必要に応じて request、pagination、decode 等を内部で行い、1つの Resource を完全に open する。

利用可能な runtime から default Adapter を選べる設計を許容し、必要に応じて利用者が明示指定できる。

---

## 22. 外部ライブラリの依存方針

v0.5 では依存を次のように考える。

### 22.1 Coreの依存関係

Core 全体に必要で軽量なもの。

HTTP transport 等を含む。

### 22.2 提供元／通信仕様ごとの追加依存

特定 Source を正しく扱うための専門ライブラリ。

例:

```text
estat -> pyestat
stac -> pystac-client / pystac
rdf -> rdflib
```

概念的には次のような installation を許容する。

```text
rhinestone[estat]
rhinestone[stac]
rhinestone[rdf]
```

実際の extra 名は packaging 設計時に決定する。

### 22.3 実行用Runtime

GDAL、Rasterio、pyogrio 等、データを開くための runtime。

利用者環境側で既に管理されているライブラリを利用可能にする。

provider specialist と execution runtime を機械的に完全分離することは目的にしない。同じ専門ライブラリが discovery / inspection / open の複数段階を担当する方が provider semantics を正しく保てる場合は、それを優先する。

---

## 23. Credential（認証情報）

Credential は SourceDefinition / Config / portable Resource specification と分離する。

```text
SourceDefinition = 公開可能な接続先・固定仕様
Config           = 対象指定
Credential       = secret
Resource spec    = 解決済み non-secret 情報
```

API key、token 等を metadata / provenance / serialization に混入させてはならない。

---

## 24. 代表的な Source の責務

### 24.1 e-Stat（統計データ）

```text
search
-> 統計表候補
-> metadata / dimensions inspection
-> statsDataId / selection resolution
-> estat-api Resource
-> pyestat open
```

日本の地域 identity、時点表現等の共有知識を利用してよいが、e-Stat の dimension code への翻訳は EStatAdapter の責務とする。

### 24.2 CKAN / G空間情報センター

```text
package / dataset
-> resources / distributions
-> concrete file / service Resource
```

CKAN API 自体を最終データ形式として扱うのではなく、通常は distribution の実 Resource を解決する。

### 24.3 横断 catalog

search.ckan.jp 等は discovery-only Source として扱える。

```text
cross-catalog search
-> SearchResult
-> target Config
-> actual provider / direct resolution
```

Rhinestone 自身は同等の全国 index を再構築しない。

### 24.4 STAC（衛星画像等のカタログ）

```text
STAC search
-> Item
-> Asset
-> concrete Resource (COG / vector / etc.)
```

STAC protocol semantics は専門ライブラリへ委譲し、Rhinestone は Resource selection と provenance を担う。

### 24.5 PLATEAU（3D都市モデル）

```text
catalog dataset
-> year / city / package
-> distribution / archive
-> entry point
-> concrete Resource
```

PLATEAU 固有 semantics は Adapter に閉じ込め、自治体 identity 等の共有可能部分だけ Japan shared knowledge を利用する。

### 24.6 GSI

GSI 固有の配布仕様、GML、tile、測地系等を理解し、最終的な Resource は GDAL / Rasterio / pyogrio 等へ渡せる状態へ解決する。

---

## 25. 直接指定するResource

既に最終 URI と format が分かっている場合、Rhinestone を通す価値が小さいことを認める。

```text
https://example.com/foo.gpkg
  ↓
pyogrio.read_dataframe(...)
```

で十分なら直接利用してよい。

Rhinestone の価値は、利用者が知っている指定と、実際に利用可能なデータとの間に解決すべきギャップがある場合に大きい。

```text
A. 欲しいものしか分からない
   -> search + resolve

B. dataset / identifier は分かる
   -> resolve

C. 最終 URI / format / reader まで分かる
   -> direct reader でもよい
```

`direct` は便利な Core 機能として維持できるが、Rhinestone の独自価値の中心とはみなさない。

---

## 26. Intake との棲み分け

Rhinestone は Intake を再実装しない。

概念的な境界は次とする。

```text
Rhinestone
= 何を使うべきかを discovery / resolve する

Intake
= 既知の data entry / reader を catalog として管理・利用する
```

Rhinestone の結果を Intake へ export する interoperability は有用である。

```text
Rhinestone discovery / resolution
  ↓
Resource
  ↓
Intake-compatible entry / catalog
```

まず一方向 export を優先し、Rhinestone の内部モデルを Intake のモデルへ置き換えない。

任意 Intake driver から Rhinestone Resource への逆変換は、意味が保てる subset に限定する。

---

## 27. AI／GISとの連携

AI / MCP / GIS は Rhinestone Core の責務ではなく integration target である。

理想的な構成例:

```text
GIS context / user intent
  ↓
AI
  ↓
Rhinestone search / resolve
  ↓
portable Resource
  ↓
local specialist runtime
  ↓
GIS / analysis
```

MCP 経由では巨大な native data object を転送するより、SearchResult / Config / portable Resource specification を渡し、実データはクライアント側で open する構成を優先する。

---

## 28. エラー方針

Rhinestone は「便利さ」のために provider facts を推測しない。

失敗すべき例:

```text
resourceが複数あり選択不能
STAC data assetが一意に決まらない
archive entry pointが特定できない
未知 format
必要 credential 不足
対象 Source が検索条件を有意味に扱えない
```

日本固有 normalization についても、同名自治体等で一意に決まらない場合は曖昧性を返す。

「日本特化」は magic guess を増やすことではなく、公式仕様・決定的ルール・provider metadata に基づく解決能力を増やすことである。

---

## 29. 拡張方針

新しい Source を追加するときは、次を優先する。

1. その Source が discovery / resolution のどちらを提供するかを決める
2. 既存 specialist library が provider semantics を正しく扱えるか確認する
3. 日本共有知識で再利用できる部分と provider 固有部分を分ける
4. SearchResult / Config / Resource へ必要な provenance を保持する
5. 最終 Resource を既存 runtime へ渡せるようにする
6. transformation / analysis を Adapter に持ち込まない

新しいカテゴリ体系や抽象クラスを追加する前に、複数 Source で同じ問題が繰り返されていることを確認する。

---

## 30. v0.5 の不変条件

以下を v0.5 の重要な不変条件とする。

1. 検索なしでも `Config -> resolve -> Resource` が成立する
2. 検索は `SearchResult -> Config -> resolve` の通常経路へ合流する
3. discovery Source と resolution target は異なってよい
4. 1 Source の検索条件非対応で federated search 全体を失敗させない
5. 日本固有知識はテーマ taxonomy ではなく横断的 resolution knowledge として持つ
6. provider 固有 semantics は Adapter または専門ライブラリに閉じ込める
7. `Resource` は URL だけに縮退させず metadata / provenance / access knowledge を保持する
8. `resolve()` は transformation / analysis を行わない
9. `open()` は provider / format の自然な native object を返してよい
10. Execution Adapter chaining を Core の前提にしない
11. credential を Config / Resource serialization に含めない
12. 全国 metadata index / scraping infrastructure を Core に要求しない
13. 既存 catalog と specialist OSS を積極的に upstream / runtime として再利用する
14. 内部知識が増えても公開 API を不必要に増やさない
15. 根拠のない推測より明示的失敗を選ぶ

---

## 31. v0.4 からの主な変更

v0.5 では v0.4 の Knowledge / Specification Layer の考え方を維持しつつ、焦点をより明確にする。

### 31.1 `resolve()` を中心に再定義

v0.4 は Source / AccessPlan / Execution Adapter の構造説明が中心だった。

v0.5 は、利用者が知っている要求・identifier と実際に利用可能な Resource の間を埋める `resolve()` を中心価値として明示する。

### 31.2 日本特化を強化

日本特化を provider の一覧だけで表現せず、地域 identity、時点、空間体系、表記、provenance 等の共有解決知識として扱う。

テーマ category は Core に導入しない。

### 31.3 discovery と resolution を分離

`SearchResult.source_id == resolve source_id` の前提を外し、横断 catalog を upstream discovery source として利用できるようにする。

### 31.4 federated search semantics を変更

全 searchable Source が全条件を支持しなければ失敗する方式をやめ、Source capability へ query を projection する方向へ変更する。

### 31.5 specialist library policy を強化

pyestat、pystac-client、rdflib 等を単なる user-provided runtime として扱うだけでなく、provider semantics の専門実装として Source Adapter 内から利用することを認める。

### 31.6 持ち運び可能なResourceの境界

Resource に保持した解決情報を、credential / live runtime と分離して serialization / MCP / Intake 等へ利用できる方向を明文化する。

---

## 32. 成功条件

Rhinestone が独立した framework / SDK として価値を持つかは、次で評価する。

5つ程度の主要 Source（例: e-Stat、CKAN / G空間情報センター、STAC、PLATEAU、GSI）について、

```text
discovery result / known identifier
  ↓
provider-specific resolution
  ↓
executable Resource
  ↓
native runtime
```

のギャップを検証する。

少なくとも複数 Source で、`resolve()` が単なる URL passthrough や driver args の薄い再包装ではなく、利用者側の provider-specific code を実質的に減らせなければならない。

この条件を満たさない場合は、独立 framework を拡張するのではなく、Intake plugin や provider-specific integration への縮小を再検討する。

---

## 33. 最終的な設計目標

利用者が日本の公共データの配布事情を詳しく知らなくても、表側の操作は小さいままであることを目指す。

```python
# 探す場合
results = app.search("...")
resource = app.resolve(results[0])
data = resource.open()

# 既に対象が分かっている場合
resource = app.resolve(config)
data = resource.open()
```

実装内部では必要に応じて、

```text
日本固有の identity / time / space normalization
provider catalog search
identifier / distribution / asset resolution
archive / encoding / access specification
credential binding
specialist library integration
provenance preservation
```

を行う。

しかしその複雑さを利用者へそのまま露出しない。

> 古い日本の公共データ配布基盤に、現代的な developer experience を被せる。

これを Rhinestone v0.5 の設計目標とする。
