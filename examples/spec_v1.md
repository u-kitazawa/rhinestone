# Rhinestone Example 仕様書 v0.1

## 1. 目的

`examples/` は、単なるサンプルコード置き場ではない。

以下の3つを同時に満たすことを目的とする。

1. 実装の動作確認
2. Rhinestoneの設計思想の実証
3. README・発表・紹介時のデモ

Exampleは、Rhinestoneが「何を便利にするライブラリなのか」を最短で理解できる内容とする。

---

## 2. Exampleで示すべき価値

Exampleでは特に以下を示す。

### 2.1 異なるProviderを同じ取得モデルで扱える

CKAN、e-Stat、STAC等は実際の提供方式が大きく異なる。

しかしRhinestone利用者からは、

```python
resource = rs.fetch(config)
```

という共通した取得モデルで扱えることを示す。

---

### 2.2 Normalize Access, Not Data

RhinestoneはすべてのデータをGeoDataFrame等へ統一しない。

統一するのは、

> データへのアクセス方法

である。

Exampleでは、取得結果がResourceとして保持され、その後必要なOSSへ渡される構造を示す。

---

### 2.3 Specによる知識の利用

Exampleでは、単純なURL取得だけでなく、

```text
format
archive
media type
encoding
layer
provider metadata
access method
provenance
```

など、Rhinestoneが保持する知識が実際のアクセスに利用されることを示す。

---

### 2.4 User-Owned Runtime Dependencies

GDAL、Rasterio、pyogrio等はRhinestoneの固定依存としない。

Exampleでは、必要に応じてユーザー環境のruntime dependencyをcallbackとして注入する構造を示す。

---

## 3. ディレクトリ構成

初期構成を以下とする。

```text
examples/
├ 01_direct_resource.py
├ 02_ckan_shapefile.py
├ 03_estat_population.py
├ 04_inspect_resource.py
├ 05_gdal_dependency.py
├ 06_stac_cog.py
└ 07_search_and_fetch.py
```

番号は、理解しやすい学習順序を表す。

---

# 4. 01_direct_resource.py

## 4.1 目的

Rhinestoneの最小構成を示す。

Provider固有APIを利用せず、既知のResourceを直接扱う。

最初に読むExampleとして利用する。

---

## 4.2 示す内容

```text
Config
  ↓
［DirectAdapter］
  ↓
Source
  ↓
［Resolver］
  ↓
Resource
```

---

## 4.3 要件

Exampleは以下を示す。

- Direct URLをConfigとして渡せる
- Resourceを取得できる
- URIを確認できる
- formatを確認できる
- Metadataを確認できる
- Provenanceを確認できる

---

## 4.4 概念例

```python
config = {
    "source": {
        "type": "direct",
        "uri": "https://example.jp/data.geojson",
        "format": "geojson",
    }
}

resource = rs.fetch(config)

print(resource.uri)
print(resource.format)
print(resource.metadata)
print(resource.provenance)
```

---

# 5. 02_ckan_shapefile.py

## 5.1 目的

Rhinestoneの主要な価値を最も分かりやすく示すExampleとする。

CKAN / GKAN上のResourceから、ZIP等で配布されるShapefileを解決する。

---

## 5.2 示す内容

```text
Config
  ↓
［CkanAdapter］
  ↓
Source
  ↓
［Resolver］
  ↓
Resource

Resource:
  format = shapefile
  archive = zip
  metadata = ...
  provenance = ...
```

---

## 5.3 要件

固定されたCKAN Resourceを使用する。

Exampleは以下を確認できること。

- CKAN APIからResource情報を解決できる
- download URLを取得できる
- format情報を保持できる
- Dataset / Resource Metadataを保持できる
- Provenanceを保持できる
- ZIP等のResource属性を保持できる

---

## 5.4 アピールポイント

Exampleから、

> CKAN APIを直接理解しなくても、データResourceとして扱える

ことが伝わること。

単なるCKAN API wrapperに見えないよう、Resource解決後の情報も表示する。

---

# 6. 03_estat_population.py

## 6.1 目的

ファイル配布型ではないProviderも、同じRhinestoneモデルで扱えることを示す。

e-Statを代表例とする。

---

## 6.2 示す内容

```text
Config
  ↓
［EStatAdapter］
  ↓
Source
  ↓
［Resolver］
  ↓
AccessPlan
  ↓
Resource
```

e-StatではResourceが単純なファイルURLである必要はない。

Service Queryとして表現できる。

---

## 6.3 要件

Exampleは以下を示す。

- statsDataIdを指定できる
- 必要なquery parameterを指定できる
- e-Stat Metadataを取得・保持できる
- ServiceQuery型AccessPlanを構築できる
- Provenanceを保持できる
- CKAN Exampleと同様に `rs.fetch(config)` から開始できる

---

## 6.4 重要事項

CKANとe-Statで実際の内部処理を無理に共通化しない。

Exampleで示すべきなのは、

> 内部構造が異なっても利用者のアクセスモデルを統一できる

ことである。

---

# 7. 04_inspect_resource.py

## 7.1 目的

Rhinestoneが単なるダウンロードライブラリではないことを示す。

RhinestoneのKnowledge / Specification Layerとしての性質を最も直接的に確認するExampleとする。

---

## 7.2 要件

取得したResourceについて、可能な範囲で以下を表示する。

```text
URI
format
media type
archive
encoding
layer
Metadata
Source information
AccessPlan
Provenance
```

---

## 7.3 概念例

```python
resource = rs.fetch(config)

print(resource.uri)
print(resource.format)
print(resource.media_type)
print(resource.metadata)
print(resource.access_plan)
print(resource.provenance)
```

---

## 7.4 アピールポイント

以下の差が明確に見えること。

```text
単なるdownload library
→ URL / local path

Rhinestone
→ Resource + Metadata + AccessPlan + Provenance
```

---

# 8. 05_gdal_dependency.py

## 8.1 目的

Execution AdapterとUser-Owned Runtime Dependencyの設計を示す。

---

## 8.2 示す内容

```text
Resource
  ↓
［Execution Adapter Selector］
  ↓
［GdalAdapter］
  ↓
［Dependency Registry］
  ↓
user-provided GDAL
```

---

## 8.3 要件

ユーザーがGDAL runtimeをcallbackとして登録する。

概念例:

```python
from osgeo import gdal

rs = Rhinestone(
    dependencies={
        "gdal": lambda: gdal,
    }
)
```

その後、

```python
dataset = resource.open()
```

または必要に応じて、

```python
dataset = resource.open(adapter="gdal")
```

を実行できることを示す。

---

## 8.4 重要事項

Exampleから、

> ユーザーが［GdalAdapter］を実装するのではない

ことが明確でなければならない。

ユーザーが提供するのはGDAL runtimeのみである。

［GdalAdapter］の知識とResourceからGDALへの変換処理はRhinestone側が所有する。

---

## 8.5 アピールポイント

次のメッセージが伝わること。

> Rhinestone does not own your GDAL.  
> Rhinestone knows how to use your GDAL.

---

# 9. 06_stac_cog.py

## 9.1 目的

クラウドネイティブ地理空間データとの親和性を示す。

STAC AssetからCOG等のRaster Resourceを解決する。

---

## 9.2 示す内容

```text
STAC
  ↓
［StacAdapter］
  ↓
Source
  ↓
［Resolver］
  ↓
COG Resource
  ↓
［Execution Adapter］
  ↓
GDAL / Rasterio
```

---

## 9.3 要件

Exampleは以下を示す。

- STAC Item / Assetを指定できる
- Asset Metadataを保持できる
- media typeを保持できる
- COG等のformatを認識できる
- remote access可能なResourceとして扱える
- GDALまたはRasterio等へ接続できる

---

## 9.4 アピールポイント

CKAN ShapefileとSTAC COGという全く異なる配信方法をRhinestoneが扱えることを示す。

---

# 10. 07_search_and_fetch.py

## 10.1 目的

Rhinestoneの最終的な利用体験を示すデモ用Exampleとする。

---

## 10.2 示す内容

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
rs.fetch()
  ↓
Resource
```

---

## 10.3 概念例

```python
results = rs.search("行政区域")

for result in results:
    print(result.title)

config = results[0].config
resource = rs.fetch(config)

print(resource.metadata)
```

---

## 10.4 重要事項

このExampleは検索Providerの外部状態に影響されるため、決定的な動作確認には使用しない。

README、デモ、発表等のアピール用途を中心とする。

---

# 11. Exampleの分類

Exampleは用途別に以下の3種類として扱う。

## 11.1 Deterministic Example

固定された入力やfixtureで再現性を確保する。

対象:

```text
01_direct_resource.py
04_inspect_resource.py
05_gdal_dependency.py
```

CIまたはtestから再利用可能であることが望ましい。

---

## 11.2 Live Integration Example

実際の公開Providerへアクセスする。

対象:

```text
02_ckan_shapefile.py
03_estat_population.py
06_stac_cog.py
```

外部Providerの状態に依存するため、通常のunit testとは分離する。

---

## 11.3 Demo Example

見栄え・体験を優先する。

対象:

```text
07_search_and_fetch.py
```

README、発表、MCPデモ等で利用する。

---

# 12. Example共通ルール

すべてのExampleは以下を守る。

## 12.1 短くする

Example自身に複雑な処理を書かない。

目安として、Rhinestoneの本質部分は20〜40行程度に収める。

---

## 12.2 Provider APIを直接叩かない

Example内で独自HTTP処理を実装しない。

悪い例:

```python
requests.get(...)
json["result"]["resources"]
```

良い例:

```python
resource = rs.fetch(config)
```

Provider固有処理は［Source Adapter］の責務とする。

---

## 12.3 Example固有の推測を入れない

Exampleを動かすためだけに、

```text
ZIPなら最初の.shpを選ぶ
format文字列を勝手に変換する
URLからproviderを推測する
```

等のロジックを書いてはならない。

必要な知識はRhinestone本体へ追加する。

---

## 12.4 Metadata / Provenanceを見せる

最低でも主要Exampleでは、単なる取得結果だけでなくMetadataまたはProvenanceを表示する。

RhinestoneのKnowledge Layerとしての価値を可視化するためである。

---

## 12.5 データ解析を主目的にしない

Example内で高度なGIS解析や統計解析を行わない。

例えば、

```text
buffer
overlay
spatial join
machine learning
```

等は原則として対象外とする。

Rhinestoneの責務はアクセスまでである。

---

# 13. READMEで使用する代表Example

README冒頭では、最も短い統一APIを示す。

```python
ckan = rs.fetch(ckan_config)
estat = rs.fetch(estat_config)
stac = rs.fetch(stac_config)
```

続いて、

```text
CKAN
e-Stat
STAC
OGC
  ↓
Rhinestone
  ↓
Resource
  ↓
GDAL / Rasterio / pyogrio / etc.
```

という構造を示す。

---

# 14. Before / After

Rhinestoneの価値を説明するため、READMEでは必要に応じてBefore / Afterを示す。

## Without Rhinestone

```text
API仕様を調べる
dataset IDを解釈する
resourceを探す
download URLを得る
formatを判定する
archiveを判定する
encodingを調べる
GDAL向けURIを作る
open optionを設定する
```

## With Rhinestone

```python
resource = rs.fetch(config)
data = resource.open()
```

ただし、Rhinestoneが内部で何を知識として処理しているかも併記し、単なるmagic APIに見せない。

---

# 15. Exampleとテストの関係

Exampleとテストは目的を分離する。

```text
Test
→ behavioural contractを保証する

Example
→ 利用方法と価値を示す
```

Exampleが動くことだけをもって仕様準拠とはみなさない。

ただし、Exampleで使用するConfigやfixtureをテストから共有することは許可する。

---

# 16. Provider Fixture方針

CKAN、e-Stat、STAC、OGCについて、仕様が確定していないrequest / response contractをExampleの都合で発明してはならない。

Provider固有Exampleは、

```text
仕様確定
↓
fixture作成
↓
deterministic test
↓
Example
```

の順序を基本とする。

仕様が未確定の場合はLive Exampleに限定するか、実装を保留する。

これはRhinestoneの、

> Fail Rather Than Guess

の原則に従う。

---

# 17. 初期リリースで必須とするExample

最初の公開版では最低限以下を含める。

```text
01_direct_resource.py
02_ckan_shapefile.py
03_estat_population.py
04_inspect_resource.py
05_gdal_dependency.py
```

これにより、

- 最小利用
- ファイル配布型Provider
- API / Service型Provider
- Spec / Metadata保持
- 外部OSS連携

を一通り実証できる。

---

# 18. 推奨実装順序

実装順序は以下とする。

```text
1. 01_direct_resource.py
2. 04_inspect_resource.py
3. 02_ckan_shapefile.py
4. 05_gdal_dependency.py
5. 03_estat_population.py
6. 06_stac_cog.py
7. 07_search_and_fetch.py
```

最初にCoreのResourceモデルを実証し、その後Provider対応、Execution Adapter、検索へ広げる。

---

# 19. 成功条件

Example群が完成した状態では、第三者がコードを見て以下を理解できなければならない。

1. Rhinestoneは何を解決するライブラリなのか
2. CKANとe-Statのような異なるProviderをどう統一するのか
3. Resourceが単なるURLではないこと
4. Metadata / Provenanceを保持する理由
5. GDAL等をRhinestoneが固定依存として所有しないこと
6. ［Execution Adapter］とruntime dependencyの違い
7. Spec / Knowledge Layerという設計思想
8. 検索からResource取得までの将来的な利用フロー

---

# 20. Exampleの中心メッセージ

Example全体を通じて、以下が伝わることを最終目標とする。

> Rhinestoneはデータ形式やProviderを隠蔽するための巨大な抽象化ではない。

> 各Provider・Resource・既存OSSについての正しい知識をSpecとして保持し、その知識を使ってデータへのアクセスを単純化する。

つまりExampleは、

> 「RhinestoneはSpecを武器に何をしてくれるのか」

を実際に動くコードで示すものである。