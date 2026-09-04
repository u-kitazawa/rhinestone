# 検証とエラー

## エラー階層

予期される Library Error はすべて `RhinestoneError` から派生する。内部の不変条件への違反などの Programming Error は、無差別にラップしない。

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

`LoaderUnavailable` は、Plan が指定する Binding が Registry に存在しなくなったことを表す。`CapabilityUnavailable` は、解決時に選択可能な Binding がなかったこと、または提示された Binding に必要な任意 Library を Import できなかったことを表す。

## 段階ごとの責務

| 段階 | 検証対象 | 代表的なエラー |
| --- | --- | --- |
| Config | 構造とユーザーが表明した内容 | `InvalidConfig` |
| Reference | 対象を識別するための十分な情報 | `InvalidReference` |
| Inspect | Provider Response と Provenance | `MetadataInvalid` |
| Resolve | 対応可能なアクセスと利用可能な Capability | `UnsupportedFormat` |
| Execute | 正確な Loader Binding と Resource Access | `ResourceUnavailable` |

下位層の `ValueError`、HTTP Exception、外部 Library の Exception が、予期される境界での失敗を表す場合、それを主要な公開 Exception として露出してはならない（MUST NOT）。診断情報を利用できるよう、公開 Error では Exception Chaining を使用する。

## Error Field

すべての `RhinestoneError` は次を持つ。

```text
code: stable machine-readable string
message: safe human-readable description
context: JSON-compatible, non-secret diagnostic mapping
```

Code には小文字の Dot 区切り識別子を使用する。例：

```text
config.missing_field
metadata.ckan_unsuccessful
metadata.identifier_mismatch
resolution.unsupported_format
resolution.capability_unavailable
execution.resource_unavailable
```

呼び出し元は Exception Class または `code` によって処理を分岐してもよい（MAY）。Message Text は安定した API ではない。

## 秘密情報と Payload の取り扱い

Error に Credential、Authorization Header、Dataset Body 全体、無制限の Provider Response を含めてはならない（MUST NOT）。Provider Error の診断情報には、Error Type や Message のような小さな Scalar Field を保持することが望ましい（SHOULD）。成功時の生 Metadata は `SourceMetadata` に保持し、各 Error へ重複して格納しない。

## 検証順序

複数の問題がある場合は、パイプラインの最も早い段階の問題を優先する。同一 Object 内では文書の順序で検証し、最初の Error を報告する。これにより、失敗の選択を決定的にし、必要になる前から複数 Error の集約検証を約束することを避ける。

## 再試行ポリシー

初期スライスでは、Core は暗黙の再試行を行わない。Application が提供する Transport は、宣言済みの再試行ポリシーを実装してもよい（MAY）が、再試行は有限でなければならず（MUST）、Provider が宣言した `success: false` Response を探索や Fallback の振る舞いに変えてはならない（MUST NOT）。
