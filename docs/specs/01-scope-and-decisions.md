# スコープと設計判断

## 目標

すでに特定されている公開データリソースに対して、Rhinestone は信頼できるメタデータを取得し、説明可能なアクセスプランを作成して、既存ライブラリに読み込みを委譲する。

ユーザー向けの基本的な正常系は次のとおり。

```python
data = rhinestone.load(config)
```

内部を確認できる経路は次のとおり。

```python
access_plan = rhinestone.plan(config)
data = rhinestone.execute(access_plan)
```

`plan()` はメタデータの I/O を実行してもよい（MAY）。実際のデータセットを読み込む操作は `execute()` だけである。

## 採用済みのアーキテクチャ判断

### D-001：探索を行わない

すべての Config は、必ず1つのリソースを正確に識別しなければならない（MUST）。Provider Adapter は CKAN の `resource_show` のような検索ではない取得操作を使用し、`package_search` のような検索操作を使用してはならない（MUST NOT）。

### D-002：一方向のパイプライン

パイプラインは次のとおり。

```text
Config -> DataReference -> SourceMetadata -> AccessPlan -> Execution -> Data
```

後続の段階から、それ以前の値を変更または拡充してはならない。再試行では新しい実行試行を作成し、プランは変更しない。

### D-003：Provider Adapter と Loader は別々の Port とする

Provider Adapter は Reference を Metadata に変換する。Loader は解決済みのプランを実行する。Loader はカタログへの問い合わせ、リソースの選択、フォーマットの変更を行ってはならない（MUST NOT）。

### D-004：解決処理は2つの決定的な判断で構成する

解決処理では、最初に Metadata を必要な Capability に対応付け、次に環境の Registry から Loader Binding を選択する。フォーマットポリシーは Capability 名を認識するが、ライブラリ名は認識しない。Registry は実装を認識するが、Provider の規則は認識しない。

最終的な `AccessPlan` には、必要な Capability と選択された Binding の両方を記録する。これにより、外部 OSS への依存を Domain パッケージに持ち込むことなく、プランを実行可能かつ説明可能にする。

### D-005：URL からフォーマットを推測しない

Resolver は、URI の接尾辞、クエリパラメーター、リダイレクト、レスポンス本文からフォーマットを推測してはならない（MUST NOT）。文書化された Alias Table を使用して、Provider が明示したフォーマットまたは Media Type を正規化してもよい（MAY）。どちらからも一意で対応可能なフォーマットが得られない場合、解決処理は失敗する。

### D-006：境界をまたぐ値を不変にする

Config、Reference、正規化された Metadata、Capability、Plan は Value Object とする。構築後に観測可能な状態が変化してはならない（MUST NOT）。Provider の生 Metadata は JSON 互換データとして欠損なく保持し、呼び出し元が内部状態を変更できない形で公開しなければならない（MUST）。

### D-007：同期 API を優先する

v0.x では同期 API を公開する。Network Port と Loader Port は将来、非同期版を追加してもよい（MAY）が、初期 API は Awaitable を返したり、隠れた Event Loop を実行したりしてはならない（MUST NOT）。

### D-008：Python 3.7 の対応を維持する

公開型と実装の構文は Python 3.7 で有効でなければならない（MUST）。Python 3.7 の対応を終了した依存関係は、プロジェクト全体で互換性に関する明示的な判断を行わない限り必須にできない。

## 明示的に先送りする項目

- データセットおよびカタログの探索
- e-Stat、OGC API、STAC、GKAN 固有の振る舞い、PLATEAU
- YAML の解析と公開 JSON Schema
- キャッシュポリシー、再試行、認証、Checksum
- ZIP 圧縮された Shapefile、GeoJSON、Raster、Table の Loader
- 公開されたサードパーティ Plugin API
- Metadata Overlay とデータ検証の自動化

先送りとは、その機能を追加できる境界を設計に残すことを意味する。最初の実装に、公開 API のプレースホルダーを含めるという意味ではない。

## 未解決の課題

次の課題は、具体的な2番目の垂直スライスまたはユーザーニーズが現れてから結論を出す。

1. `plan()` は `AccessPlan` のみを返すべきか、それとも Reference、Metadata の要約、検証結果、Plan を含むレポートを返すべきか。
2. 任意の YAML 対応には PyYAML を使用すべきか、より厳格な YAML 実装を使用すべきか。
3. Loader Binding の優先順位はパッケージ、ユーザー、またはその両方のどこで定義すべきか。
4. e-Stat の安定した戻り値仕様とする表形式の型は、PyArrow Table、pandas DataFrame、呼び出し元が選択する型のどれか。
5. Metadata Overlay は Config に含めるべきか、独立した Trust Policy の入力に含めるべきか。

課題1が解決するまでは、`plan()` は `AccessPlan` を返す。診断用の入力は、その Plan の Field または Provenance として引き続き参照できるようにする。
