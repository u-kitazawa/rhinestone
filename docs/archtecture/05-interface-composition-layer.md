# Interface / Composition 層仕様

## 責務と制約

この層は、利用者へ最小の同期 API を公開し、既定の Application と Adapter 構成を組み立てる。Domain の意味を変更せず、隠れた探索、Event Loop、Process-global な登録変更を行わない。

## Public API

初期の Top-level API は次の意味を持つ。

```python
config = parse_config(mapping)
access_plan = plan(config_or_mapping)
data = execute(access_plan)
data = load(config_or_mapping)
```

### `parse_config()`

Memory 上の Mapping を受け取り、不変 Config を返す。Path String を JSON、YAML、Local Path、URI のいずれかに推測してはならない（MUST NOT）。文書入力を将来追加する場合は `load_config(path)` のような明示境界にする。

### `plan()`

Config または Mapping を受け取り、不変 AccessPlan を返す。Metadata I/O を行ってよいが、Dataset を読み込まず、Loader OSS を Import しない（MUST NOT）。診断 Report ではなく Plan を返す。診断情報は Plan の Field と Decision Record から取得できるようにする。

### `execute()`

AccessPlan だけを受け取る。Config、Reference、生 URI を受け付けて暗黙に Plan を作ってはならない（MUST NOT）。選択済み Loader の戻り値を変更せず返す。

### `load()`

意味的に `execute(plan(config))` と等価でなければならない（MUST）。中間 Plan を差し替えたり、再解決したりしてはならない（MUST NOT）。

## Application Composition

既定 Application は、組み込みの Reference Factory、Metadata Adapter、Capability Binding、Loader、Transport を遅延構築してよい（MAY）。構築結果は呼び出しごとに意味が変わらないようにし、明示的な Application Instance と同じ契約を満たす。

任意 Module の利用可能性は、Import を伴わない発見機構で調べて Binding を提示してよい（MAY）。発見結果は実行成功の保証ではない。実行時 Import が失敗した場合は対応する Capability Error に変換する。

高度な利用とテスト向けに、すべての Registry と Port を Constructor Injection できる `Application` を提供する。Constructor は Process-global Registry を変更せず、同じ構成から同じ選択順序を作る（MUST）。

## 公開エラー境界

予期される Library Error はすべて `RhinestoneError` から派生し、少なくとも次を持つ。

```text
code: stable lowercase dot-separated identifier
message: safe human-readable description
context: finite JSON-compatible diagnostic mapping
```

最低限、次の原因を型で区別する。

```text
RhinestoneError
├── InvalidConfig
├── UnsupportedSourceType
├── InvalidReference
├── MetadataError
│   ├── MetadataUnavailable
│   └── MetadataInvalid
├── ResolutionError
│   ├── UnsupportedProtocol
│   ├── UnsupportedFormat
│   └── CapabilityUnavailable
├── InvalidQuery
├── ExecutionError
│   ├── ResourceUnavailable
│   └── IntegrityError
└── LoaderUnavailable
```

Exception Class と `code` は分岐可能な安定契約であり、Message Text は安定 API ではない。外部の `ValueError`、HTTP Exception、OSS Exception を予期される主例外として漏らしてはならない（MUST NOT）。Programming Error や内部不変条件違反まで無差別に `RhinestoneError` へ包んではならない（MUST NOT）。

## 戻り値契約

- `parse_config()` は不変 Config を返す。
- `plan()` は不変な具象 AccessPlan を返す。
- `execute()` と `load()` は Loader 固有の Object をそのまま返す。
- Rhinestone は異なる Capability 間で共通 DataFrame 型や地理空間型を保証しない。
- 呼び出し元は Plan の Capability と Binding から戻り値の生成契約を確認できる。

## API 安定性

v0.x でも Top-level Function 名、Exception Class、Error Code、Config Shape、Capability Identifier、シリアライズされた Plan Field は互換性影響を評価する（MUST）。内部 Registry と Adapter Constructor は、公開 Plugin API として宣言されるまでは内部詳細として変更してよい（MAY）。

Python の公開型と実装構文は、プロジェクト全体で別の互換性判断を記録しない限り `requires-python = ">=3.7"` を満たさなければならない（MUST）。初期 API は Awaitable を返したり、隠れた Event Loop を起動したりしてはならない（MUST NOT）。

## 適合テスト

- Top-level API と注入構成の Application が同じ契約を満たす。
- `plan()` は Dataset I/O を行わず、`execute()` は Metadata I/O を行わない。
- `load()` の結果と外部呼び出し回数が明示合成と一致する。
- Mapping の変更が Config、Plan に伝播しない。
- 公開失敗は安定した Class と Code を持ち、Cause を保持する。
- Error、Plan、診断シリアライズに秘密情報が含まれない。
