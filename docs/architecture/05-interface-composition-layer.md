# Interface / Composition 層仕様

> **文書ステータス: 履歴資料。** v0.4の設計を実装境界へ整理した文書で、現行APIの契約ではありません。現在の参照先は[ドキュメントの位置付け](../documentation-status.md)を確認してください。

## 責務

この層は、Config から Resource を得る操作、Resource を実行する操作、横断検索、依存と Adapter の構成を利用者へ公開します。Core モデルの意味を変えたり、隠れた探索や変換を追加したりしません。

## 利用インターフェース

公開 API は次の意味的操作を提供します。

- Config を検証して適切な Source Adapter へ渡す。
- Source を解決し、AccessPlan を保持する Resource を返す。
- SearchQuery を検索 Capability のある Adapter へ渡して SearchResult を返す。
- SearchResult を通常フローで利用できる Config へ変換する。
- Resource を自動選択または明示指定された Execution Adapter で開く。
- Resource、Metadata、Provenance を実行せず参照する。

具体的な function/class 名は公開 API の実装とともに定義します。概念的な `resource.open(adapter="gdal")` は、明示選択可能な実行境界を表します。

## Composition

Application 構成は Adapter Registry と Dependency Registry を組み立て、Resolver、Search Coordinator、Execution Adapter Selector へ注入します。Process-global な可変登録へ Domain を依存させません（MUST NOT）。

利用者は runtime dependency を callback/factory として登録します。既定構成が optional module の存在を調べる場合も、Core がその version を所有したり直接 import したりしてはなりません（MUST NOT）。

## 公開失敗

少なくとも Config、provider communication/response、resolution、unsupported condition、Adapter selection、dependency、Resource access、integrity の失敗を区別します。公開エラーは安全な診断情報と元の原因を保持し、credential や無制限 payload を含めません。

## 戻り値

Resource 解決操作は Metadata、Provenance、AccessPlan、Source を保持する Resource を返します。実行操作は外部 OSS の自然な結果型を尊重します。全 Adapter に共通 DataFrame 型や Rhinestone 独自データ形式を要求しません。
