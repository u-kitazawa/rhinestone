# 調整コンポーネント仕様

> **文書ステータス: 履歴資料。** v0.4の設計を実装境界へ整理した文書で、現行APIの契約ではありません。現在の参照先は[ドキュメントの位置付け](../documentation-status.md)を確認してください。

## 責務と制約

この層は Core データと Adapter を調整し、provider 固有処理や外部 OSS の処理自体は実装しません。

## ［Resolver］（解決処理）

Source に含まれる Resource 候補から利用対象を選び、そのアクセス方法を AccessPlan として確定し、Resource を構成します。

- Source に明示された Metadata と Capability だけを判断材料にする（MUST）。
- データ本体を原則として読み込まない（MUST NOT）。
- provider API の request を組み立てない（MUST NOT）。
- format、protocol、候補の曖昧さを silent fallback で解消しない（MUST NOT）。
- 決定理由を診断可能にする（SHOULD）。

## ［Search Coordinator］（検索の調整役）

SearchQuery を検索 Capability のある Source Adapter へ配布し、SearchResult を集約します。

- provider が対応しない条件を黙って除去しない（MUST NOT）。
- provider 固有 ranking score を直接比較しない（MUST NOT）。
- 結果を provider ごとのまとまりとして保持する（MUST）。
- reranking を行う場合は exact title match、official provider、Metadata completeness 等の共通信号だけを使用する（MUST）。

## ［Execution Adapter Selector］（実行アダプターの選択）

Resource の性質と Dependency Registry で利用可能な runtime をもとに Execution Adapter を決定します。

- 同じ Resource と利用可能 dependency から同じ Adapter を選ぶ（MUST）。
- Registry の偶然の登録順へ依存しない（MUST NOT）。
- 利用者が Adapter を明示した場合は、その指定を検証して使用する（MUST）。
- 利用可能な適合 Adapter がない場合は明示的に失敗する（MUST）。

## 構成順序

1. Adapter Registry から Source Adapter を取得する。
2. Config を Source Adapter へ渡して Source を得る。
3. Resolver が AccessPlan と Resource を確定する。
4. Selector が Execution Adapter を決定する。
5. Execution Adapter が Dependency Registry を通じて外部 OSS を利用する。

検索時は Search Coordinator が SearchResult を返し、利用する結果を Config へ変換した後に手順1へ入ります。
