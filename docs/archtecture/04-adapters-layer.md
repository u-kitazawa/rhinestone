# Adapter 層仕様

## ［Source Adapter］

### 責務

provider 固有の Config、API、Metadata、resource 構造を解釈し、Source を生成します。検索 Capability を持つ Adapter は公式 API から SearchResult を生成します。

### 契約

1. Config の明示 field を検証する。
2. 公式の機械可読インターフェースに request する。
3. response の schema と意味を検証する。
4. 共通 Metadata、Resource 候補、Capability、Provenance を抽出する。
5. raw metadata と確定した情報を保持した Source を返す。

HTML scraping、endpoint/download URL の推測、非公式 DOM 構造への依存を行ってはなりません（MUST NOT）。公式インターフェースがなければ unsupported とします。

Source Adapter の内部で HTTP 通信まで行えます。外部契約を安定させ、Client 等への内部分割は必要性に応じて行います。

## ［Execution Adapter］

### 責務

Resource が持つ provider/format/access knowledge を、外部 OSS が理解する呼び出しへ翻訳します。例えば ZIP Shapefile の Resource から GDAL の `/vsizip/` URI、open option、layer を構築します。

### 契約

1. Resource と AccessPlan が Adapter の対応条件を満たすことを確認する。
2. Dependency Registry から利用者提供の runtime を取得する。
3. URI、option、layer/subdataset 等を決定的に構築する。
4. 外部 OSS に処理を委譲する。
5. 外部失敗を原因別の境界エラーへ変換する。

Execution Adapter は Resource を選択せず、独自の file parser、GIS engine、暗黙の format/CRS/data 変換を実装しません（MUST NOT）。

## 適合テスト

すべての Adapter は offline fixture と fake dependency で、入力からの変換、情報保持、外部呼び出し、非対応入力、schema 不正、dependency 不在、外部失敗を検証します。新しい Adapter は代表例と共通契約テストを同じ垂直スライスに含めます。
