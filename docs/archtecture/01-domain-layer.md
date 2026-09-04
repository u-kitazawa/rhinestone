# Domain 層仕様

## 責務と制約

Domain 層は、配信元や実装技術に依存しない意味的な Value Object と不変条件を定義する。すべての Value Object は構築後に観測可能な状態が変わってはならず（MUST NOT）、外部から渡された可変 Object を共有してはならない（MUST NOT）。

Domain 層は Network、Filesystem、環境変数、時計、Registry、外部 OSS を参照しない。配信元名、API Endpoint の組み立て規則、外部ライブラリ名による分岐を持ってはならない（MUST NOT）。

## DataReference

### 責務

`DataReference` は「どの Source Object を指すか」を一意に表す。識別方式が異なる場合は具象 Value Object を持ってよい。

### 契約

- 対象を一意に識別するために必要十分な値だけを保持する（MUST）。
- Loader、Capability、Format、Timeout、Cache、Credential を保持してはならない（MUST NOT）。
- Identifier の欠落、空文字、不正な URI など、識別を成立させない値を拒否する（MUST）。
- 正規化は、末尾区切り文字など意味を変えないことが仕様で保証された操作に限定する（MUST）。Endpoint や Resource を探索して補ってはならない（MUST NOT）。
- 値による等価性と安全な診断表現を提供することが望ましい（SHOULD）。

### 適合テスト

同じ入力から等しい Reference が生成されること、元入力の変更が Reference に伝播しないこと、不正な識別値が `InvalidReference` になることを確認する。

## ResourceMetadata

### 責務

`ResourceMetadata` は、配信元が直接アクセス可能と表明した1つの表現を記述する。

### 最小モデル

```text
ResourceMetadata
  identifier: non-empty source identifier
  uri: absolute resource URI
  format: optional source-provided label
  media_type: optional source-provided media type
  title: optional title
```

### 契約

値が存在しないことと、存在するが空または不正であることを区別する（MUST）。Format と Media Type は配信元の表記を保持し、この Value 自身が正規 Format や Capability を決めてはならない（MUST NOT）。URI は配信元が明示した値であり、接尾辞や Redirect から補完してはならない（MUST NOT）。

## SourceMetadata

### 責務

`SourceMetadata` は、配信元が表明した事実、その取得元、直接アクセス可能な表現をまとめる。Config の主張や Loader の都合を混ぜない。

### 最小モデル

```text
SourceMetadata
  identifier: non-empty identifier
  title: optional title
  license: optional expression or label
  authority: source authority URI or identifier
  resources: non-empty ordered tuple of ResourceMetadata
  raw: losslessly retained JSON-compatible response
  provenance: MetadataProvenance
```

### 契約

- `resources` の配信元順序を保持する（MUST）。複数候補を受け入れる場合は、Resolver 側に明示的で決定的な選択規則が必要である。
- `raw` は取得した成功 Response を欠損なく保持し、呼び出し元から変更できない形で公開する（MUST）。
- 正規 Field は `raw` の値と矛盾してはならない（MUST NOT）。派生値や Overlay を導入する場合は、Source Assertion と区別し Provenance を付ける。
- 欠落情報を推測して埋めてはならない（MUST NOT）。追加 I/O が明示された Adapter 契約に含まれない限り、Field を埋めるためだけの通信を行わない。

## MetadataProvenance

### 責務

Metadata の取得経路を説明し、監査を可能にする。

```text
MetadataProvenance
  provider: stable adapter identifier
  retrieved_from: exact machine-readable endpoint
  retrieved_at: optional UTC timestamp
```

`retrieved_at` のような観測値は、同じ Source Assertion の意味的等価性や Plan の等価性に影響してはならない（MUST NOT）。Provenance に認証情報付き URI や秘密 Header を含めてはならない（MUST NOT）。

## Capability

### 責務

`Capability` は、データへアクセスするために必要な意味的能力を安定した識別子で表す。Format や外部ライブラリ名の別名ではない。

### 契約

- 小文字の Dot 区切りなど、文書化された安定形式を使用する（SHOULD）。
- 実装製品名、Version、インストールパスを含めてはならない（MUST NOT）。
- 異なる入力・出力意味論を同じ Capability にまとめてはならない（MUST NOT）。
- Capability の追加時は、入力 Plan と戻り値の意味、Loader 適合条件を仕様化する（MUST）。

## LoaderBinding

### 責務

`LoaderBinding` は、環境が提示する1つの Loader 実装と Capability の対応を表す。

```text
LoaderBinding
  identifier: stable implementation identifier
  capability: capability identifier
  priority: integer
```

Binding 自体は実装を Import せず、利用可能性の提示だけを表す。候補は `(priority, identifier)` の昇順で選択し、Identifier は同順位時の決定的 Tie-breaker とする（MUST）。

## AccessPlan

### 責務

`AccessPlan` は「何を、どのアクセス方式で、どの Binding に渡すか」の選択が完了した状態を表す。File、Remote Dataset、Service Query などアクセス形態ごとの具象型を持ってよいが、共通不変条件を満たさなければならない（MUST）。

### 共通契約

すべての Plan は次を保持する。

- 対象を実行するための明示的な Locator または Query。
- 正規化済みの Format または Protocol。
- 必要 Capability。
- 選択された LoaderBinding。
- Source Object を追跡できる Identifier。
- 非自明な判断を順序付きで示す Decision Record。

Plan は完全かつ不変でなければならない（MUST）。実行時探索を必要とする候補一覧、暗黙の Default、Credential を含めてはならない（MUST NOT）。Loader の Identifier と Capability は対応していなければならない（MUST）。

### Decision Record

各 Record は安定した機械可読 Code、判断入力、判断結果を持つ。少なくとも Resource 選択、Format/Protocol の正規化、Capability 選択、Binding 選択のうち発生した非自明な判断を記録する。人間向け Message だけを契約にしてはならない（MUST NOT）。秘密情報と生 Response 全体を記録してはならない（MUST NOT）。

## シリアライズと等価性

Domain Value は JSON 互換の診断用シリアライズを提供することが望ましい（SHOULD）。シリアライズは Plan の意味と判断を理解できる情報を保持し、秘密情報を含めてはならない（MUST NOT）。デシリアライズは Credential、Registry、実装 Version の寿命を別途定義するまで契約しない。

等価性にはすべての意味的 Field を含め、取得時刻など非意味的と明記された観測値を除外する。同等の意味入力から生成された Plan は等しくなければならない（MUST）。
