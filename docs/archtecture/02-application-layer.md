# Application 層仕様

## 責務と制約

Application 層はユースケースを調整し、Domain Value と Port を接続する。配信元プロトコルや外部 Loader API を実装せず、具象 Adapter を Import しない。Resolver 以外のコンポーネントがアクセス方法を決定してはならない（MUST NOT）。

## Config Parser

### 責務

Memory 上の Mapping を検証し、不変の `Config` へ変換する。JSON/YAML/File の Decode は別の入力境界であり、Parser の責務ではない。

### 契約

- Root と Nested Field の構造、型、必須 Field、未知 Key を検証する（MUST）。
- Boolean、Number、Null、Collection を String へ暗黙変換しない（MUST NOT）。
- 前後空白を暗黙に除去しない（MUST NOT）。意味を変えないと仕様化された正規化だけを行う。
- URI Credential を拒否し、Config に秘密情報を保持しない（MUST）。
- 入力 Mapping を深く分離し、解析後の入力変更から Config を保護する（MUST）。
- Network、Filesystem、時計、Registry、任意 Import を使用しない（MUST NOT）。

構造または値が不正なら `InvalidConfig`、構造は有効だが Application が判別値を扱えないなら `UnsupportedSourceType` とする。

## Reference Factory

### 責務

Config の識別情報を対応する `DataReference` に写像する。

### 契約

Factory の選択は Config の明示的な判別値との完全一致で行う（MUST）。Factory は副作用を持たず、Format、Capability、Loader、Metadata を追加してはならない（MUST NOT）。識別に不足があれば `InvalidReference` とする。

## Metadata Inspection Coordinator

### 責務

Reference の型に完全一致する Metadata Adapter を Registry から1つ選び、検査を1回実行する。

### 契約

- Adapter がない場合と複数に曖昧一致する場合を、固有の構成または対応不能 Error として失敗させる（MUST）。
- Fallback として別 Adapter、別 Endpoint、検索 API、HTML を試さない（MUST NOT）。
- Adapter が返した Metadata を変更せず Resolver へ渡す（MUST）。
- 1回の `plan()` 呼び出しで同じ Reference を重複検査しない（MUST NOT）。

## Resolver

### 責務

Reference、SourceMetadata、Requirements、Capability Registry から、実行可能で説明可能な AccessPlan を決定する。Resolver は「Metadata から必要 Capability を決める判断」と「Capability から Binding を決める判断」を分離する。

### 入出力

```text
DataReference + SourceMetadata + Requirements + CapabilityRegistry
  -> AccessPlan | ResolutionError
```

### 解決手順

1. Reference と Metadata が同じ Source Object を指すことを検証する。
2. 明示された規則で対象 Resource または Service Operation を1つに決める。
3. Provider が明示した Format、Media Type、Protocol を文書化された Policy で正規化する。
4. 正規表現から必要 Capability を1つに決める。
5. Capability Registry の Binding を完全順序で並べ、1つを選ぶ。
6. 各判断の Decision Record を含む Plan を構築する。

### 禁止事項

Resolver は Network、Filesystem、Resource 本体、外部 Loader Import を使用してはならない（MUST NOT）。URI 接尾辞、Redirect、Response 本文の試し読みから Format を推測してはならない（MUST NOT）。未知値を似た既知値へ変換したり、Library 名を条件に Format Policy を変えたりしてはならない（MUST NOT）。

### エラー

Protocol が未対応なら `UnsupportedProtocol`、Format が欠落または未対応なら `UnsupportedFormat`、明示情報が競合するなら `MetadataInvalid`、必要 Binding がなければ `CapabilityUnavailable` とする。

## Resolution Policies

Resolver の判断規則は、Resource Selection、Format / Protocol Canonicalization、Capability Mapping、Binding Selection の小さな Policy に分離してよい（MAY）。Policy は Domain Value と明示 Table だけを入力とする純粋なコンポーネントであり、配信元名や具象 Loader 名によって分岐してはならない（MUST NOT）。

Format と Media Type の Alias、Protocol と Capability の対応は、明示 Table として管理する。比較時の大文字小文字、Parameter の扱い、競合時の優先順位を Table ごとに定義しなければならない（MUST）。

未知値を URI、Content、インストール済み OSS から推測してはならない（MUST NOT）。Format と Media Type が共に認識可能で競合する場合は `MetadataInvalid`、情報不足または未知なら対応する `Unsupported*` Error とする。Table の追加は種類固有の分岐ではなく、標準または明示 Source Assertion から Canonical Value への一般的な規則として行う。

各 Policy は、同じ入力から同じ結果または同じ Error を返し、採用した規則を安定した Decision Record として返せなければならない（MUST）。

## Executor

### 責務

AccessPlan に記録された Binding と完全一致する Loader を Registry から取得し、その Plan を1回実行する。

### 契約

- 実行時に Capability や代替 Loader を再選択しない（MUST NOT）。
- 選択済み Binding が存在しなければ `LoaderUnavailable` とする（MUST）。
- Loader に Config、Reference、Metadata ではなく Plan だけを渡す（MUST）。
- Loader の戻り値を変換、Copy、検証せず、そのまま返す（MUST）。Data Validation を提供する場合は別の明示ユースケースとする。

## Application

### 責務

Application は Registry と各ユースケースを所有し、次の合成を提供する。

```text
plan(config) = parse -> reference -> inspect -> resolve
execute(plan) = lookup selected loader -> load
load(config) = execute(plan(config))
```

Constructor Injection により独立した Registry、Fake Transport、Fake Adapter、Fake Loader を使用できなければならない（MUST）。Process-global Registry を暗黙に変更してはならない（MUST NOT）。

`load(config)` は、その呼び出し内で作成された同一 Plan を実行し、Metadata Inspection と Loader 呼び出しをそれぞれ1回だけ行う（MUST）。戻り値と例外の意味は個別ユースケースと一致しなければならない（MUST）。

## Requirements

Requirements は、呼び出し元が明示した結果またはアクセス上の制約だけを表す。暗黙の環境状態や Provider Default を混ぜない。具体的な選択ニーズが複数の実例で確認されるまでは内部 Value とし、Option のない単一状態でよい。公開 API に先行して拡張 Point を設けてはならない（MUST NOT）。

## 適合テスト

- Parser、Factory、Resolver は同じ入力に対して決定的で、副作用がない。
- Inspection は正しい Adapter を1回だけ呼ぶ。
- Resolver は Registry 登録順に依存せず、全判断を Plan に記録する。
- Executor は Plan が指定した Loader 以外を呼ばない。
- `load(config)` と `execute(plan(config))` の観測可能な結果が一致する。
- 各段階は、自身より後段の I/O を開始しない。
