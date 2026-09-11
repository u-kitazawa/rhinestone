# スコープと設計原則

> **文書ステータス: 履歴資料。** v0.4の設計を実装境界へ整理した文書で、現行APIの契約ではありません。現在の参照先は[ドキュメントの位置付け](../documentation-status.md)を確認してください。

## 目的

Rhinestone は、日本の公的・地理空間データについて、配信元から既存 OSS へ接続するための知識を提供します。対象を宣言した Config を解釈し、Metadata と Provenance を保持した Resource、Resource へのアクセス方法を表す AccessPlan、外部ライブラリ向けの実行設定を生成します。

## 所有するもの

- Config の解釈
- Source、Metadata、AccessPlan、Resource、Provenance
- provider、format、protocol、access に関する知識
- Source Adapter、Resolver、Search Coordinator
- Execution Adapter Selector、Execution Adapter
- Adapter Registry、Dependency Registry

## 所有しないもの

- GIS I/O、ファイル解析、Raster/Vector 処理、形式変換、データ解析
- GDAL、Rasterio、pyogrio、PyArrow、QGIS 等の runtime とバージョン
- 公式データの再ホスティング
- 必須の中央検索インデックス
- Core における HTML scraping
- すべてのデータを単一型へ変換する処理

## 設計原則

1. Core を軽量に保つ。
2. 既存標準と OSS を優先する。
3. データではなくアクセス方法を正規化する。
4. 暗黙の推測より明示性を優先する。
5. 確定した Metadata と Provenance を保持する。
6. runtime dependency は利用者が所有する。
7. 不確かな処理は失敗させるか opt-in を要求する。
8. Core では HTML scraping を行わない。
9. 検索は各 provider の公式 API を使う federated search とする。
10. 既存 FOSS4G ecosystem と直接接続できる設計を保つ。
11. 中央インフラを必須にしない。
12. 機能を Spec / Knowledge の追加として設計する。

## 決定性

同一の Config、Metadata、利用可能な Capability からは、同一の AccessPlan が得られなければなりません（MUST）。候補選択と Adapter 選択の規則は、登録順や偶然の環境状態に依存せず説明可能でなければなりません（MUST）。
