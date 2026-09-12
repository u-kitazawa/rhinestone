# Spatial Knowledge Adapter（空間参照と範囲意味）

## 1. 目的

Spatial Adapterは、異なるProviderが使う座標参照系（CRS）、軸順、bbox、タイル、地域
メッシュの意味を明示し、検索条件とResource Metadataの取り違えを防ぐ。空間値を受け取って
別の座標系へ変換すること自体が目的ではない。まず「この数値は何の座標で、どの順序で、どの
境界規則に従うか」を確定する。

OGC API Features Part 2は、`bbox-crs`が指定されない場合のbboxをCRS84として扱う契約を
定めている。一方、他のAPIやファイル形式には異なる軸順・既定CRSがあり得るため、Rhinestone
内部の共通値がそのまま全Providerへ送れるとは仮定しない。[OGC API Features Part 2](https://docs.ogc.org/is/18-058r1/18-058r1.html)

## 2. 概念モデル

```text
SpatialExpression
  ├─ bbox + CRS + axis order
  ├─ mesh code + mesh system + level
  └─ explicit CRS reference
          ↓ validation / provider projection
SpatialKnowledge
  ├─ canonical CRS reference
  ├─ coordinate order
  ├─ domain / boundary semantics
  ├─ provider-accepted representations
  └─ evidence
```

最小のbboxは `(west, south, east, north)` のような数値列だけでなく、CRS、軸順、境界の
包含規則を持つ。経度緯度を扱うCRS84と、緯度経度の軸を定義する別表現を同一視しない。
CRS識別子は文字列として保持し、定義や変換パラメータが必要なときは専用Runtimeへ委譲する。

```yaml
bbox:
  values: [139.68, 35.65, 139.76, 35.72]
  crs: "OGC:CRS84"
  axis_order: [longitude, latitude]
  boundary: closed
```

## 3. CRS、軸順、再投影

CRSはEPSG番号だけでなく、authorityとcodeの組として入力・出力に残す。WKTのような完全な
CRS定義を受け取った場合も、Knowledge Adapterが独自に短縮して意味を失わせない。OGCの
WKT CRS標準はCRSと座標操作の表現を規定するが、実際の読み書きや変換処理を指定するものでは
ない。[OGC WKT CRS](https://www.ogc.org/standards/wkt-crs/)

次の規則を採用する。

- 入力にCRSがない場合、Provider契約に既定値があるときだけ適用し、その根拠を記録する。
- CRS84を既定とするAPIの条件を、ファイルや別APIへ一般化しない。
- 軸順はCRS名から推測せず、Providerまたは標準の契約から確定する。
- 再投影はKnowledge Adapterの必須責務にしない。変換する場合は、使用した定義・ライブラリ・
  変換誤差・変換前後のCRSをProvenanceへ残す。
- 高さ（ellipsoidal height / orthometric height）を2次元bboxへ黙って落とさない。

「EPSG:4326なら常にx,y」という実装慣行に依存することは危険である。Rhinestoneの内部値
は、利用者とProviderの双方が軸順を確認できる形を優先する。

## 4. bboxと時間・境界の意味

bboxは矩形範囲であり、行政界、データの完全なcoverage、タイル境界を意味しない。東西端が
反転している入力を日付変更線越えと解釈するか、単純な不正値とするかはProvider契約に従う。
共通初期契約では、反転を推測せず失敗する。

境界の包含規則も保持する。`closed`、`half-open`、Provider未定義を区別し、検索結果を
「範囲内」と説明できるようにする。bboxと`datetime`を併用する場合、空間条件が観測時点へ
適用されるのか、Resourceの有効期間へ適用されるのかを別Metadataにする。

## 5. メッシュとタイル

日本の地域メッシュコードやProvider固有のmesh IDは、コードそのものを一意の空間ポリゴン
として扱うのではなく、体系・レベル・値を保持する。メッシュからgeometryを生成する機能は、
規格と変換アルゴリズムを明示できる別機能であり、初期Adapterでは行わない。

XYZ、TMS、WMTS等のタイル識別は、`scheme`、ズーム範囲、原点、行方向、画像形式、coverage、
attributionをまとめて保持する。URL末尾や拡張子からschemeを推測しない。GSIのような静的
タイルはSource Adapterで配信情報を解決し、Spatial Adapterはタイル座標の意味を共有する。

## 6. Source／Resolver／Executionとの境界

Source Adapterは、Providerのクエリパラメータ、既定CRS、許容bbox、meshのコード体系を解釈
する。Knowledge Adapterは、値を検証し、Provider向け投影が情報を失わないかを判定する。
Resolverは、複数ResourceのcoverageやCRSを見て選択するが、座標変換を理由に候補を勝手に
書き換えない。Execution Adapterは、選択済みResourceをGDALやRasterio等へ渡し、必要なら
利用者が指定したRuntimeの変換機能を呼ぶ。

Knowledge Adapterは地図表示、空間演算、ポリゴン生成、再サンプリングを担当しない。

## 7. 失敗と検証

| 状況 | 期待する扱い |
| --- | --- |
| CRSが不正・不明 | validation / unsupported CRS |
| 軸順が不明 | ambiguous spatial reference |
| bboxの順序・範囲が不正 | validation error |
| ProviderのCRSへ損失なく投影できない | unsupported projection |
| mesh体系・レベルが不明 | unknown mesh |
| 日付変更線処理が契約外 | fail rather than guess |

テストでは、CRS84の正常bbox、軸順違い、緯度経度範囲外、反転bbox、3次元値、meshレベル、
ProviderがCRS84だけを受ける場合の投影拒否を固定する。シリアライザの出力が元の意味を保持
するかを、数値だけでなくCRSと軸順について検証する。

## 8. 最小垂直スライスと延期

最初は、明示CRS付きbboxとmesh identifierを不変値として検証し、OGC API Features等の
Provider Adapterが宣言した形式へ投影する範囲が適切である。これにより、検索条件の軸順
事故を減らし、Resource Metadataへ空間根拠を残せる。

CRSデータベースの同梱、無償・有償変換グリッド、ポリゴンからの自動行政区域判定、地図投影の
最適化は延期する。これらは外部Runtimeとデータ更新の責任を伴い、共有知識の最小契約を超える。

## 9. 参考資料

- [OGC API Features](https://ogcapi.ogc.org/features/)
- [OGC API Features Part 2: CRS by Reference](https://docs.ogc.org/is/18-058r1/18-058r1.html)
- [OGC WKT CRS](https://www.ogc.org/standards/wkt-crs/)
- [統計LOD 地域に関するデータ](https://data.e-stat.go.jp/lodw/provdata/lodRegion)
