# Adapters 層仕様

## 責務と制約

Adapters 層は、外部の Protocol、Service、Transport、OSS を Ports と Domain Value に変換する。種類固有の振る舞いはこの層に閉じ込めるが、アーキテクチャ上はすべて同じ Adapter 契約に従う。種類ごとに別階層を作ってはならない（MUST NOT）。

## Source Metadata Adapter

### 責務

DataReference を、配信元の正式な Machine-readable Interface へ正確に対応付け、Response を SourceMetadata に変換する。

### 処理契約

1. Reference の明示 Field から、文書化された Protocol 規則で Request を構築する。
2. 許可された Metadata Operation だけを必要最小回数実行する。
3. Envelope、Status、必須 Field、型、Identifier 一致、Resource URI を順に検証する。
4. Source Field を Canonical Field に対応付け、生 Response と Provenance を保持する。
5. 不変な SourceMetadata を返す。

Adapter は検索 Operation、HTML DOM、CSS Selector、XPath、Regex による HTML 抽出、推測した Endpoint、Resource への Probe を使ってはならない（MUST NOT）。不足 Field を補うための追加 Request は、その Adapter 契約で明示されない限り行ってはならない（MUST NOT）。

Source Identifier と要求した Identifier の不一致は別 Resource の発見ではなく `MetadataInvalid` とする。配信元が成功と宣言していない Response は `MetadataUnavailable` とし、成功 Response 内の構造不正と区別する。

### 拡張規則

新しい Source Adapter は、既存の DataReference、SourceMetadata、MetadataAdapter Port で表現できるかを先に検討する。追加する場合は代表 Fixture、正確な Request、期待 Metadata、失敗 Matrix、共通契約テストを同じ垂直スライスに含める（MUST）。Provider 名による分岐を Resolver や Domain に追加してはならない（MUST NOT）。

## Transport Adapter

### 責務

Transport Port の Request を既存通信 Library に委譲し、Response または境界エラーへ変換する。

### 契約

- URI、Method、Body を意味的に変更しない（MUST NOT）。Percent Encoding など Protocol が要求する表現変換は、二重 Encoding を避け決定的に行う。
- Timeout は有限とし、Redirect と Retry の Policy を構成可能または文書化する（MUST）。
- TLS 検証を既定で無効にしない（MUST NOT）。
- Authorization、Cookie、Credential 付き URI、Response Body 全体を Error Context や Log に出さない（MUST NOT）。
- Decode 失敗と通信失敗を、呼び出し側 Adapter が原因を識別できる形で伝える。

Transport Adapter は Cache や Checksum を将来合成してよいが、Metadata Request と Dataset Request の責務を混同せず、利用を明示的な Policy とする。

## Loader Adapter

### 責務

選択済み AccessPlan を、対応 Capability を実現する既存 OSS の最小操作へ写像する。

### 処理契約

1. Plan の具象型、Capability、Binding Identifier が Adapter 契約と一致することを確認する。
2. 任意 OSS を実行境界で Import または取得する。
3. Plan Field を OSS の引数へ機械的に写像する。
4. OSS を1回呼び、成功結果を変更せず返す。
5. 予期される外部失敗を原因付きの Rhinestone Error へ変換する。

Loader は便利そうな候補選択、Path 推測、Temporary Download、Layer 自動選択、形式・Schema・座標変換を追加してはならない（MUST NOT）。OSS が URI を直接扱える場合は、その能力へ委譲することが望ましい（SHOULD）。中間保存が Capability 上必要なら、Cache/Transport Policy と Lifecycle を別途仕様化する。

### 拡張規則

新しい Loader Adapter は既存 Capability を実装するか、新しい意味的 Capability が必要な理由を示す。外部ライブラリごとに Domain 型を増やしてはならない（MUST NOT）。適合テストでは Fake OSS Boundary を用い、引数、呼び出し回数、結果の同一性、Import 失敗、Resource 失敗を確認する。

## Adapter 適合テスト

すべての Adapter は Offline で次を検証する。

- 代表的な完全 Fixture から期待する Domain Value または OSS 呼び出しが得られる。
- Input と Fixture が変更されない。
- 正常系の外部呼び出し回数と引数が正確である。
- 探索、Probe、Fallback、暗黙変換が発生しない。
- 欠落、型不正、Identifier 不一致、通信失敗、外部 OSS 失敗が別の Error になる。
- Error Context に秘密情報や無制限 Payload が含まれない。

Live Test は Protocol の実環境適合を補助的に確認するもので、通常 PR の必須 Offline Test と分離する。変動する Title、件数、Timestamp、Availability を不変の仕様として Assert してはならない（MUST NOT）。
