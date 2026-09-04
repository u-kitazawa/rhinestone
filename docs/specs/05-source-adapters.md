# Source Adapter 契約

## 責務

Source Adapter は外部 provider と Core の境界です。Config の provider 固有項目、API request、response schema、resource 構造、format 表現を理解し、Core が扱える Source を生成します。

例として CKAN Adapter は resource identifier、package/resource 構造、resource URL、format、metadata structure を理解します。e-Stat Adapter は statsDataId、統計表 Metadata、dimension、category、area、time、API query を理解します。

## 共通契約

Source Adapter は次を満たさなければなりません。

- 公式の machine-readable interface を使用する（MUST）。
- provider 固有 Reference と response structure を Adapter 内部に閉じ込める（MUST）。
- 解釈済みの共通情報と raw metadata を Source に保持する（MUST）。
- Resource 候補、Capability 情報、Metadata、Provenance を欠落させない（MUST）。
- HTML DOM、CSS selector、XPath、headless browser、HTML regex を使用しない（MUST NOT）。
- download URL や未提示 format を推測しない（MUST NOT）。

公式 API、STAC API、OGC API、DCAT、documented REST/GraphQL API、direct resource URL などの確実なインターフェースがない provider は unsupported とします。

## Search Capability

検索を提供する Adapter だけが search Capability を宣言します。未対応条件を黙って無視せず、結果には Config へ戻るための provider 固有情報、Metadata、Provenance を含めます。

## Adapter Registry

Source Adapter と Execution Adapter の登録状態は Adapter Registry が管理します。初期実装では内部 Registry を使用し、外部拡張機構は反復可能な契約が実例で確認された場合に設計します。
