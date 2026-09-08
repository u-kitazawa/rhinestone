# Core データ層仕様

> **文書ステータス: 履歴資料。** v0.4の設計を実装境界へ整理した文書で、現行APIの契約ではありません。現在の参照先は[ドキュメントの位置付け](../documentation-status.md)を確認してください。

## 責務と制約

Core データ層は、Rhinestone が所有する知識を外部ライブラリから独立したモデルとして表現します。GDAL、Rasterio、pyogrio、QGIS 等を import してはなりません（MUST NOT）。

## Config

対象データを宣言します。Source type と、その Source Adapter が必要とする設定を持ちます。実行時依存や OSS option は持ちません。

## Source

Source Adapter が provider を解釈した結果であり、Metadata、Resource 候補、Capability 情報、Provenance、source-specific raw metadata を保持します。provider 固有 Reference 型は持ちません。

## Metadata

共通利用される最小限の field と、provider が返した raw metadata を保持します。共通 schema に合わせるために元の情報を破棄してはなりません（MUST NOT）。

## AccessPlan

Resource へのアクセス方法を表します。File、remote dataset、service query 等の違いを型または明示的 field で表現し、外部 OSS の module instance は持ちません。

## Resource

URI、format、media type、Metadata、Provenance、AccessPlan、Source、必要に応じて local path を保持します。解決済み知識を一体として後続処理へ渡します。

## Provenance

provider、identifier、endpoint、original URL、query parameter、retrieved time、checksum、Adapter 情報、raw metadata など、取得と解決の経路を保持します。

## SearchQuery / SearchResult

SearchQuery は provider 横断で意味が共有できる最小限の条件だけを持ちます。SearchResult は表示用情報だけでなく、provider 固有 Config、Metadata、Provenance を保持します。

## 等価性と保持

意味的に同じ入力は同じ解決結果を作らなければなりません（MUST）。retrieved time のような観測値を等価性へ含める場合も、選択結果が非決定的にならない規則を明示します。モデルをシリアライズする場合は、知識を保持しつつ credential を除外します。
